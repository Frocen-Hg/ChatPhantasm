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
from ..memory.retriever import effective_importance, rank_score, similarity
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
        .where(
            Memory.character_id == character_id,
            Memory.visibility == "public",
            Memory.decay_at.is_(None),  # 已衰减归档的记忆不参与注入
        )
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


def estimate_tokens(text: str) -> int:
    """粗略 token 估算：CJK 约 1 字 1 token，其余约 4 字符 1 token"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk + (len(text) - cjk + 3) // 4


def _truncate_to_tokens(text: str, limit: int) -> str:
    """把文本截断到约 limit token（二分，尽量保留前部）"""
    if estimate_tokens(text) <= limit:
        return text
    if limit <= 0:
        return ""
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if estimate_tokens(text[:mid]) <= limit:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo]


def _fit_history(history: list[dict], limit: int) -> list[dict]:
    """从最新往旧取历史消息直至超预算；至少保留最新一条（截断）"""
    picked: list[dict] = []
    used = 0
    for m in reversed(history):
        cost = estimate_tokens(m["content"])
        if used + cost > limit:
            break
        picked.append(m)
        used += cost
    if not picked and history:
        last = history[-1]
        picked = [
            {"role": last["role"], "content": _truncate_to_tokens(last["content"], max(limit, 16))}
        ]
    return list(reversed(picked))


async def build_context(
    db: AsyncSession,
    character: Character,
    conversation_id: int,
    user_content: str,
) -> list[dict]:
    """组装本轮请求的完整消息列表：L0 token 预算内按优先级分配各区块。

    分配顺序（被裁剪顺序的逆）：角色卡/内心状态（固定）→ L1 历史 → L3 长期记忆 → L2 摘要。
    即预算不足时先裁长期记忆、再裁摘要、最后才动历史。
    """
    mem_cfg = character.ext.get("memory") or {}
    window = int(mem_cfg.get("window", settings.memory_window))
    top_k = int(mem_cfg.get("top_k", settings.memory_top_k))
    half_life = float(mem_cfg.get("half_life_days", settings.memory_half_life_days))
    budget = int(mem_cfg.get("budget_tokens", settings.context_budget_tokens))
    recent_n = int(mem_cfg.get("query_recent", settings.memory_query_recent))

    raw_history = await load_history(db, conversation_id, limit=window)

    # 检索 query：最近 N 条消息 + 当前输入，缓解「那它呢？」这类指代检索不到的问题
    query = " ".join(m["content"] for m in raw_history[-recent_n:] if m["content"])
    query = f"{query} {user_content}".strip()

    # 固定区块：角色卡 + 内心状态（不裁剪）
    blocks = ["[角色卡]\n" + compose_system_prompt(character.card)]
    used = estimate_tokens(blocks[0])
    inner = _format_state(await db.get(CharacterState, character.id))
    if inner:
        blocks.append(inner)
        used += estimate_tokens(inner)
    remaining = max(budget - used, 0)

    # L1 历史：占剩余预算上限 60%，从最新往回取
    history = _fit_history(raw_history, int(remaining * 0.6))
    remaining -= sum(estimate_tokens(m["content"]) for m in history)

    # L3 长期记忆：在剩余 60% 内按 rank 顺序放入（放不下的跳过）
    memories = await retrieve(db, character.id, query, top_k, half_life)
    picked: list[Memory] = []
    cap = int(remaining * 0.6)
    cost = 0
    for m in memories:
        item_cost = estimate_tokens(m.content)
        if cost + item_cost > cap:
            continue
        picked.append(m)
        cost += item_cost
    if picked:
        blocks.append("[长期记忆]\n" + "\n".join(f"- {m.content}" for m in picked))
        remaining -= cost

    # L2 摘要：用剩余预算，超出则截断
    summary = await latest_summary(db, character.id, conversation_id)
    if summary and remaining > 0:
        text = _truncate_to_tokens(summary.content, remaining)
        if text:
            blocks.append("[会话摘要]\n" + text)

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
    source_start_id: int | None = None,
    source_end_id: int | None = None,
) -> None:
    """一轮对话结束后：抽取事实入库（L3，含溯源与去重合并），按阈值触发摘要（L2）与惰性衰减"""
    mem_cfg = character.ext.get("memory") or {}
    items = await extractor.extract_memories(
        provider, model_cfg, character.name, user_msg, assistant_msg
    )
    threshold = float(mem_cfg.get("dedupe_threshold", settings.memory_dedupe_threshold))
    for it in items:
        existing = await _find_duplicate(db, character.id, it["kind"], it["content"], threshold)
        if existing is not None:
            _merge_memory(existing, it["content"], it["importance"])
        else:
            db.add(
                Memory(
                    character_id=character.id,
                    conversation_id=conversation_id,
                    layer="L3",
                    kind=it["kind"],
                    content=it["content"],
                    importance=it["importance"],
                    visibility="public",
                    source_start_id=source_start_id,
                    source_end_id=source_end_id,
                )
            )

    state = await get_or_create_state(db, character.id)
    state.last_user_at = datetime.now()
    await db.commit()

    every = int(mem_cfg.get("summarize_every", settings.summarize_every))
    total = await _message_count(db, conversation_id)
    if every > 0 and total > 0 and total % every == 0:
        await _summarize(db, character, conversation_id, provider, model_cfg, every)
        # 与摘要同频做惰性衰减，避免每轮全表扫描
        await decay_memories(
            db,
            character.id,
            half_life_days=float(mem_cfg.get("half_life_days", settings.memory_half_life_days)),
            min_effective=float(mem_cfg.get("decay_min", settings.memory_decay_min)),
        )


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


async def _find_duplicate(
    db: AsyncSession, character_id: int, kind: str, content: str, threshold: float
) -> Memory | None:
    """在同角色同类未归档记忆中找相似度最高者（扫描最近 200 条）"""
    result = await db.execute(
        select(Memory)
        .where(
            Memory.character_id == character_id,
            Memory.kind == kind,
            Memory.decay_at.is_(None),
        )
        .order_by(Memory.id.desc())
        .limit(200)
    )
    best: Memory | None = None
    best_score = 0.0
    for m in result.scalars().all():
        score = similarity(content, m.content)
        if score > best_score:
            best, best_score = m, score
    return best if best_score >= threshold else None


def _merge_memory(memory: Memory, content: str, importance: float) -> None:
    """合并重复记忆：保留更完整的内容，重要度取大并小幅提升，记录合并次数"""
    if len(content) > len(memory.content):
        memory.content = content
    memory.importance = min(10.0, max(float(memory.importance or 0.0), importance) + 0.5)
    meta = memory.meta
    meta["merged"] = int(meta.get("merged", 0)) + 1
    memory.meta_json = json.dumps(meta, ensure_ascii=False)


async def decay_memories(
    db: AsyncSession,
    character_id: int,
    half_life_days: float | None = None,
    min_effective: float | None = None,
) -> int:
    """惰性衰减：有效重要度低于阈值 → 写 decay_at 归档，不再参与检索注入"""
    half_life = float(settings.memory_half_life_days if half_life_days is None else half_life_days)
    threshold = float(settings.memory_decay_min if min_effective is None else min_effective)
    result = await db.execute(
        select(Memory).where(Memory.character_id == character_id, Memory.decay_at.is_(None))
    )
    now = datetime.now()
    archived = 0
    for m in result.scalars().all():
        if effective_importance(m.importance, m.created_at, half_life) < threshold:
            m.decay_at = now
            archived += 1
    if archived:
        await db.commit()
    return archived


def schedule_ingest(
    character_id: int,
    conversation_id: int,
    user_msg: str,
    assistant_msg: str,
    provider,
    model_cfg: dict,
    source_start_id: int | None = None,
    source_end_id: int | None = None,
) -> None:
    """在流式响应结束后异步写入记忆，避免阻塞返回"""
    task = asyncio.create_task(
        _run_ingest(
            character_id,
            conversation_id,
            user_msg,
            assistant_msg,
            provider,
            model_cfg,
            source_start_id,
            source_end_id,
        )
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
    source_start_id: int | None,
    source_end_id: int | None,
) -> None:
    async with SessionLocal() as db:
        try:
            character = await db.get(Character, character_id)
            if character is None:
                return
            await ingest_turn(
                db,
                character,
                conversation_id,
                user_msg,
                assistant_msg,
                provider,
                model_cfg,
                source_start_id,
                source_end_id,
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


async def update_state(db: AsyncSession, state: CharacterState, payload) -> CharacterState:
    """编辑内心状态（心情/关注/关系）；P3 心跳亦可复用此写入路径"""
    data = payload.model_dump(exclude_unset=True)
    relationship = data.pop("relationship", None)
    for field, value in data.items():
        setattr(state, field, value)
    if relationship is not None:
        state.relationship_json = json.dumps(relationship, ensure_ascii=False)
    await db.commit()
    await db.refresh(state)
    return state
