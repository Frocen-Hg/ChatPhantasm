"""记忆编排：上下文组装（L0）、写入流水线（抽取 + 摘要）、检索、内心状态。

分层记忆（P1，纯 SQL）：
  L0 工作记忆 = build_context() 每轮动态组装，不落库
  L1 短期     = messages 最近 N 轮
  L2 情节     = memories(layer=L2, kind=summary) 滚动摘要
  L3 长期     = memories(layer=L3) 事实/偏好/关系
  L4 内心     = memories(layer=L4) + character_state（P3 心跳填充，P1 预留结构）
"""

import asyncio
import json
import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import Character, CharacterState, Memory, Message
from ..db.session import SessionLocal
from ..memory import extractor, summarizer
from ..memory.retriever import rank_score
from .character_service import compose_system_prompt

logger = logging.getLogger(__name__)

# 后台任务强引用集合，避免 asyncio 任务被 GC 提前回收
_bg_tasks: set[asyncio.Task] = set()


async def load_history(db: AsyncSession, conversation_id: int, limit: int) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    rows = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in rows]


async def get_or_create_state(db: AsyncSession, character_id: int) -> CharacterState:
    state = await db.get(CharacterState, character_id)
    if state is None:
        state = CharacterState(character_id=character_id)
        db.add(state)
        await db.commit()
        await db.refresh(state)
    return state


def _format_state(state: CharacterState | None) -> str:
    if state is None:
        return ""
    bits: list[str] = []
    if state.mood:
        bits.append(f"当前心情：{state.mood}")
    if state.current_focus:
        bits.append(f"当前关注：{state.current_focus}")
    if state.relationship:
        bits.append("关系状态：" + json.dumps(state.relationship, ensure_ascii=False))
    return "[内心状态]\n" + "\n".join(bits) if bits else ""


async def retrieve(
    db: AsyncSession,
    character_id: int,
    query: str,
    top_k: int,
    half_life_days: float,
) -> list[Memory]:
    """长期记忆检索：先按 importance 取候选，再关键词 × 重要性 × 衰减排序"""
    result = await db.execute(
        select(Memory)
        .where(Memory.character_id == character_id, Memory.visibility == "public")
        .order_by(Memory.importance.desc(), Memory.id.desc())
        .limit(200)
    )
    candidates = list(result.scalars().all())
    scored = [(m, rank_score(query, m, half_life_days)) for m in candidates]
    scored = [(m, s) for m, s in scored if s > 0]
    scored.sort(key=lambda pair: pair[1], reverse=True)

    picked = [m for m, _ in scored[:top_k]]
    now = datetime.now()
    for m in picked:
        m.access_count = (m.access_count or 0) + 1
        m.last_access_at = now
    if picked:
        await db.commit()
    return picked


async def latest_summary(
    db: AsyncSession, character_id: int, conversation_id: int
) -> Memory | None:
    result = await db.execute(
        select(Memory)
        .where(
            Memory.character_id == character_id,
            Memory.conversation_id == conversation_id,
            Memory.layer == "L2",
            Memory.kind == "summary",
        )
        .order_by(Memory.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def build_context(
    db: AsyncSession,
    character: Character,
    conversation_id: int,
    user_content: str,
) -> list[dict]:
    """组装本轮请求的完整消息列表，替换 P0 的「仅角色卡 + 历史」"""
    mem_cfg = character.ext.get("memory") or {}
    window = int(mem_cfg.get("window", settings.memory_window))
    top_k = int(mem_cfg.get("top_k", settings.memory_top_k))
    half_life = float(mem_cfg.get("half_life_days", settings.memory_half_life_days))

    blocks = ["[角色卡]\n" + compose_system_prompt(character.card)]

    inner = _format_state(await db.get(CharacterState, character.id))
    if inner:
        blocks.append(inner)

    memories = await retrieve(db, character.id, user_content, top_k, half_life)
    if memories:
        blocks.append("[长期记忆]\n" + "\n".join(f"- {m.content}" for m in memories))

    summary = await latest_summary(db, character.id, conversation_id)
    if summary:
        blocks.append("[会话摘要]\n" + summary.content)

    history = await load_history(db, conversation_id, limit=window)
    return [
        {"role": "system", "content": "\n\n".join(blocks)},
        *history,
        {"role": "user", "content": user_content},
    ]


async def ingest_turn(
    db: AsyncSession,
    character: Character,
    conversation_id: int,
    user_msg: str,
    assistant_msg: str,
    provider,
    model_cfg: dict,
) -> None:
    """一轮对话结束后：抽取事实入库（L3），并按阈值触发摘要（L2）"""
    items = await extractor.extract_memories(
        provider, model_cfg, character.name, user_msg, assistant_msg
    )
    for it in items:
        db.add(
            Memory(
                character_id=character.id,
                conversation_id=conversation_id,
                layer="L3",
                kind=it["kind"],
                content=it["content"],
                importance=it["importance"],
                visibility="public",
            )
        )

    state = await get_or_create_state(db, character.id)
    state.last_user_at = datetime.now()
    await db.commit()

    every = int((character.ext.get("memory") or {}).get("summarize_every", settings.summarize_every))
    total = await _message_count(db, conversation_id)
    if every > 0 and total > 0 and total % every == 0:
        await _summarize(db, character, conversation_id, provider, model_cfg, every)


async def _message_count(db: AsyncSession, conversation_id: int) -> int:
    result = await db.execute(
        select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
    )
    return result.scalar_one()


async def _summarize(
    db: AsyncSession,
    character: Character,
    conversation_id: int,
    provider,
    model_cfg: dict,
    limit: int,
) -> None:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    rows = list(reversed(result.scalars().all()))
    if not rows:
        return
    content = await summarizer.summarize(provider, model_cfg, character.name, rows)
    if not content:
        return
    db.add(
        Memory(
            character_id=character.id,
            conversation_id=conversation_id,
            layer="L2",
            kind="summary",
            content=content,
            importance=6.0,
            source_start_id=rows[0].id,
            source_end_id=rows[-1].id,
        )
    )
    await db.commit()


def schedule_ingest(
    character_id: int,
    conversation_id: int,
    user_msg: str,
    assistant_msg: str,
    provider,
    model_cfg: dict,
) -> None:
    """在流式响应结束后异步写入记忆，避免阻塞返回"""
    task = asyncio.create_task(
        _run_ingest(character_id, conversation_id, user_msg, assistant_msg, provider, model_cfg)
    )
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


async def _run_ingest(
    character_id: int,
    conversation_id: int,
    user_msg: str,
    assistant_msg: str,
    provider,
    model_cfg: dict,
) -> None:
    async with SessionLocal() as db:
        try:
            character = await db.get(Character, character_id)
            if character is None:
                return
            await ingest_turn(
                db, character, conversation_id, user_msg, assistant_msg, provider, model_cfg
            )
        except Exception as e:  # noqa: BLE001 后台任务失败不影响主流程
            logger.warning("后台记忆写入失败：%s", e)


# ---- 记忆管理（MemoryManager API 用）----


async def list_memories(
    db: AsyncSession,
    character_id: int,
    layer: str | None = None,
    kind: str | None = None,
    limit: int = 200,
) -> list[Memory]:
    stmt = select(Memory).where(Memory.character_id == character_id)
    if layer:
        stmt = stmt.where(Memory.layer == layer)
    if kind:
        stmt = stmt.where(Memory.kind == kind)
    stmt = stmt.order_by(Memory.importance.desc(), Memory.id.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_memory(db: AsyncSession, character_id: int, payload) -> Memory:
    memory = Memory(character_id=character_id, **payload.model_dump())
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return memory


async def update_memory(db: AsyncSession, memory: Memory, payload) -> Memory:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(memory, field, value)
    await db.commit()
    await db.refresh(memory)
    return memory


async def delete_memory(db: AsyncSession, memory: Memory) -> None:
    await db.delete(memory)
    await db.commit()
