"""心跳调度、内心独白与主动消息（P3a/P3b）。

复用 outbox worker 模式（与 memory_jobs / kb_jobs 同构）：heartbeat_jobs 每角色一行
配置（next_run_at 作重复调度），heartbeat_runs 记录每次执行。到期扫描时过滤
禁用 / 静默时段 / 每日上限；失败按连续失败次数退避，超过上限回到正常节奏。

两种产出：
- monologue（P3a）：memories(L4, kind=monologue, visibility=private) +
  character_state；独白为 private 不直接注入聊天上下文，通过内心状态影响对话。
- proactive（P3b）：满足空闲阈值 + 概率抖动时，落 messages(source=heartbeat)
  并同事务入队记忆任务；run 成功后经 WS 广播事件（离线回放靠 messages 历史）。
"""

import asyncio
import contextlib
import json
import logging
import random
from datetime import datetime, time, timedelta

from sqlalchemy import func, select

from ..config import settings
from ..db.models import (
    Character,
    CharacterState,
    Conversation,
    HeartbeatJob,
    HeartbeatRun,
    Memory,
    Message,
    ProviderConfig,
)
from ..db.session import SessionLocal
from ..memory import monologue, proactive
from ..memory.tokens import estimate_tokens
from . import memory_service, ws_service
from .chat_service import get_or_create_conversation, resolve_provider
from .provider_service import build_provider, get_route

logger = logging.getLogger(__name__)

SUPPORTED_TYPES = ("monologue", "proactive")
KNOWN_TYPES = ("monologue", "proactive")


# ---- 配置解析（全局默认 ← ext.heartbeat 覆盖 ← heartbeat_jobs 物化）----


def _default_config() -> dict:
    return {
        "enabled": False,  # 每角色默认关闭（风险缓解：默认不出声）
        "interval_min": settings.heartbeat_interval_min,
        "types": list(SUPPORTED_TYPES),
        "quiet_hours": {
            "start": settings.heartbeat_quiet_start,
            "end": settings.heartbeat_quiet_end,
        },
        "daily_limit": settings.heartbeat_daily_limit,
        "jitter_ratio": 0.2,
        "show_monologue": False,
    }


def resolve_config(character: Character) -> dict:
    """角色 ext.heartbeat 覆盖全局默认（行创建/显式同步时使用）"""
    cfg = _default_config()
    ext = character.ext.get("heartbeat")
    if isinstance(ext, dict):
        for key in cfg:
            if ext.get(key) is not None:
                cfg[key] = ext[key]
    return cfg


def _heartbeat_ext(character: Character) -> dict:
    ext = character.ext.get("heartbeat")
    return ext if isinstance(ext, dict) else {}


def proactive_min_idle_min(character: Character) -> int:
    """主动开口的空闲阈值（分钟）：ext.heartbeat 可覆盖全局"""
    return max(0, int(_heartbeat_ext(character).get(
        "proactive_min_idle_min", settings.heartbeat_proactive_min_idle_min
    )))


def proactive_probability(character: Character) -> float:
    """满足条件后转为主动消息的概率（0-1）：ext.heartbeat 可覆盖全局"""
    value = float(_heartbeat_ext(character).get(
        "proactive_probability", settings.heartbeat_proactive_probability
    ))
    return max(0.0, min(value, 1.0))


def _parse_hhmm(value) -> time | None:
    try:
        hour, minute = str(value).split(":")
        return time(hour=int(hour), minute=int(minute))
    except (ValueError, AttributeError):
        return None


def in_quiet_hours(now: datetime, job: HeartbeatJob) -> bool:
    """是否处于静默时段（支持跨午夜；时段无效则视为无静默）"""
    quiet = job.quiet_hours
    start = _parse_hhmm(quiet.get("start", ""))
    end = _parse_hhmm(quiet.get("end", ""))
    if start is None or end is None or start == end:
        return False
    current = now.time()
    if start < end:
        return start <= current < end
    return current >= start or current < end


def validate_quiet_hours(value: dict) -> None:
    """校验配置格式（HH:MM 或空串表示不静默），失败抛 ValueError"""
    for key in ("start", "end"):
        raw = str((value or {}).get(key, "") or "")
        if raw and _parse_hhmm(raw) is None:
            raise ValueError(f"quiet_hours.{key} 需为 HH:MM 格式")


def validate_types(types: list) -> None:
    if not types:
        raise ValueError("types 不能为空")
    for item in types:
        if item not in KNOWN_TYPES:
            raise ValueError(f"不支持的心跳类型：{item}")


async def _last_user_activity(db, character_id: int) -> datetime | None:
    """最近用户活动时间：取内心状态与最近会话中用户消息的较新者（防 last_user_at 滞后）"""
    candidates: list[datetime] = []
    state = await db.get(CharacterState, character_id)
    if state is not None and state.last_user_at is not None:
        candidates.append(state.last_user_at)
    conversation = await _latest_conversation(db, character_id)
    if conversation is not None:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id, Message.role == "user")
            .order_by(Message.id.desc())
            .limit(1)
        )
        message = result.scalar_one_or_none()
        if message is not None:
            candidates.append(message.created_at)
    return max(candidates) if candidates else None


async def choose_type(db, job: HeartbeatJob) -> str | None:
    """本轮执行类型：满足主动条件且概率命中 → proactive，否则回落 monologue。

    触发条件（P3b）：类型含 proactive + 距上次用户消息 ≥ 空闲阈值 + 概率抖动命中；
    未命中且配置含 monologue 时改为独白；两者都不可用返回 None（跳过本轮）。
    """
    types = job.types
    if "proactive" in types:
        character = await db.get(Character, job.character_id)
        if character is not None:
            last = await _last_user_activity(db, job.character_id)
            idle_ok = last is None or (datetime.now() - last) >= timedelta(
                minutes=proactive_min_idle_min(character)
            )
            if idle_ok and random.random() < proactive_probability(character):
                return "proactive"
    if "monologue" in types:
        return "monologue"
    return None


def compute_next_run_at(job: HeartbeatJob, now: datetime, *, jitter: bool = True) -> datetime:
    """下次运行时间 = now + interval × (1 ± jitter_ratio)，避免整点齐发"""
    interval = max(1, int(job.interval_min or 1))
    ratio = max(0.0, min(float(job.jitter_ratio or 0.0), 0.9))
    factor = 1.0 + random.uniform(-ratio, ratio) if jitter and ratio > 0 else 1.0
    return now + timedelta(minutes=interval * factor)


async def get_or_create_job(db, character: Character) -> HeartbeatJob:
    """取角色心跳配置行，不存在则按 ext.heartbeat/全局默认物化一行（默认关闭）

    行创建后即为运行时事实配置；面板 PUT 会同时回写 ext.heartbeat 保持角色卡可携带。
    """
    job = await db.get(HeartbeatJob, character.id)
    if job is not None:
        return job
    cfg = resolve_config(character)
    job = HeartbeatJob(
        character_id=character.id,
        enabled=bool(cfg["enabled"]),
        interval_min=max(1, int(cfg["interval_min"])),
        types_json=json.dumps(list(cfg["types"]), ensure_ascii=False),
        quiet_hours_json=json.dumps(dict(cfg["quiet_hours"]), ensure_ascii=False),
        daily_limit=max(0, int(cfg["daily_limit"])),
        jitter_ratio=max(0.0, min(float(cfg["jitter_ratio"]), 0.9)),
        show_monologue=bool(cfg["show_monologue"]),
    )
    job.next_run_at = compute_next_run_at(job, datetime.now())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


def _sync_ext(character: Character, job: HeartbeatJob) -> None:
    """把行配置回写 ext.heartbeat（角色卡导出/导入可携带）"""
    ext = character.ext
    ext["heartbeat"] = {
        "enabled": job.enabled,
        "interval_min": job.interval_min,
        "types": job.types,
        "quiet_hours": job.quiet_hours,
        "daily_limit": job.daily_limit,
        "jitter_ratio": job.jitter_ratio,
        "show_monologue": job.show_monologue,
    }
    character.ext_json = json.dumps(ext, ensure_ascii=False)


async def update_job(db, character: Character, job: HeartbeatJob, payload) -> HeartbeatJob:
    """更新心跳配置；开关/间隔/抖动变化时重排下次运行时间"""
    data = payload.model_dump(exclude_unset=True)
    if data.get("quiet_hours") is not None:
        validate_quiet_hours(data["quiet_hours"])
    if data.get("types") is not None:
        validate_types(list(data["types"]))
    reschedule = any(key in data for key in ("enabled", "interval_min", "jitter_ratio"))
    for field, value in data.items():
        if value is None:
            continue
        if field == "types":
            job.types_json = json.dumps(list(value), ensure_ascii=False)
        elif field == "quiet_hours":
            job.quiet_hours_json = json.dumps(dict(value), ensure_ascii=False)
        else:
            setattr(job, field, value)
    if job.enabled and reschedule:
        job.next_run_at = compute_next_run_at(job, datetime.now())
    _sync_ext(character, job)
    await db.commit()
    await db.refresh(job)
    return job


def blocked_reason(job: HeartbeatJob, now: datetime, today_count: int) -> str | None:
    """未运行时被拦下的原因（面板展示用；None 表示可运行）"""
    if not job.enabled:
        return "disabled"
    if in_quiet_hours(now, job):
        return "quiet_hours"
    if today_count >= int(job.daily_limit or 0):
        return "daily_limit"
    if not any(item in SUPPORTED_TYPES for item in job.types):
        return "no_type"
    return None


async def daily_run_stats(db, character_id: int, now: datetime | None = None) -> tuple[int, int]:
    """今日执行统计：(总数, 试跑数)；总数用于每日上限门控"""
    now = now or datetime.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(HeartbeatRun.is_manual, func.count(HeartbeatRun.id))
        .where(HeartbeatRun.character_id == character_id, HeartbeatRun.started_at >= day_start)
        .group_by(HeartbeatRun.is_manual)
    )
    total = 0
    manual = 0
    for is_manual, count in result.all():
        total += count
        if is_manual:
            manual += count
    return total, manual


async def job_dict(db, job: HeartbeatJob) -> dict:
    now = datetime.now()
    total, manual = await daily_run_stats(db, job.character_id, now)
    return {
        "character_id": job.character_id,
        "enabled": job.enabled,
        "interval_min": job.interval_min,
        "types": job.types,
        "quiet_hours": job.quiet_hours,
        "daily_limit": job.daily_limit,
        "jitter_ratio": job.jitter_ratio,
        "show_monologue": job.show_monologue,
        "last_run_at": job.last_run_at,
        "next_run_at": job.next_run_at,
        "due": job.next_run_at <= now,  # 调度时间已到（未启用/被拦时不会自动推进）
        "blocked_reason": blocked_reason(job, now, total),
        "today_count": total,
        "today_manual": manual,
        "quiet_now": in_quiet_hours(now, job),
        "updated_at": job.updated_at,
    }


# ---- 调度判定 ----


async def daily_run_count(db, character_id: int, now: datetime | None = None) -> int:
    """今日已执行次数（含失败与手动试跑，防止成本失控）"""
    now = now or datetime.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(HeartbeatRun.id)).where(
            HeartbeatRun.character_id == character_id,
            HeartbeatRun.started_at >= day_start,
        )
    )
    return result.scalar_one()


async def due_jobs(db, now: datetime | None = None) -> list[HeartbeatJob]:
    """到期且可运行的调度：enabled + next_run_at 已到 + 非静默 + 未超每日上限。

    静默/超限不推进 next_run_at，解禁后（如早上出静默）自然触发。
    """
    now = now or datetime.now()
    result = await db.execute(
        select(HeartbeatJob)
        .where(HeartbeatJob.enabled.is_(True), HeartbeatJob.next_run_at <= now)
        .order_by(HeartbeatJob.next_run_at)
    )
    out: list[HeartbeatJob] = []
    for job in result.scalars().all():
        if in_quiet_hours(now, job):
            continue
        if await daily_run_count(db, job.character_id, now) >= int(job.daily_limit or 0):
            continue
        out.append(job)
    return out


# ---- 执行（独白）----


_resolver_override = None  # 测试注入：async (db, character) -> (provider, model_cfg)


def set_resolver(resolver) -> None:
    global _resolver_override
    _resolver_override = resolver


async def _resolve_llm(db, character: Character):
    """心跳生成模型的解析：优先 `model_routes['heartbeat']`（可选功能位），未绑定回落聊天解析"""
    if _resolver_override is not None:
        return await _resolver_override(db, character)
    route = await get_route(db, "heartbeat")
    if route is not None and route.enabled:
        provider = await db.get(ProviderConfig, route.provider_id)
        if provider is not None:
            model_cfg: dict = {}
            if route.model:
                model_cfg["model"] = route.model
            for key, value in route.params.items():
                model_cfg.setdefault(key, value)
            model_cfg.setdefault(
                "model", provider.models[0] if provider.models else settings.default_model
            )
            model_cfg.setdefault("temperature", settings.default_temperature)
            model_cfg.setdefault("max_tokens", settings.default_max_tokens)
            return build_provider(provider), model_cfg
    return await resolve_provider(db, character)


async def _latest_conversation(db, character_id: int) -> Conversation | None:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.character_id == character_id)
        # QQ 群消息会刷新 updated_at：主动消息优先落到最近活跃的会话（进而投递到对应群）
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _time_note(state: CharacterState | None, now: datetime) -> str:
    """时间差素材：供独白提示"已经 X 小时没人说话"，不包含用户原文"""
    lines = [f"现在时间：{now.strftime('%Y-%m-%d %H:%M')}。"]
    last = state.last_user_at if state is not None else None
    if last is None:
        lines.append("你们还没有与用户对话过。")
    else:
        minutes = max(int((now - last).total_seconds() // 60), 0)
        if minutes < 60:
            lines.append(f"距离上次与用户对话已经约 {minutes} 分钟。")
        else:
            lines.append(f"距离上次与用户对话已经约 {minutes // 60} 小时。")
    return "\n".join(lines)


def _apply_state(state: CharacterState, parsed: dict) -> None:
    """把生成结果中的心情/关注/唤醒度写入内心状态（缺省字段不覆盖）"""
    mood = str(parsed.get("mood") or "").strip()
    focus = str(parsed.get("current_focus") or "").strip()
    if mood:
        state.mood = mood[:64]
    if focus:
        state.current_focus = focus[:255]
    arousal = parsed.get("arousal")
    if arousal is not None:
        state.arousal = max(0.0, min(float(arousal), 1.0))
    state.last_beat_at = datetime.now()


async def _run_monologue(db, character: Character, conversation: Conversation | None, run: HeartbeatRun) -> None:
    conv_id = conversation.id if conversation is not None else 0
    ctx = await memory_service.assemble_context(
        db, character, conv_id, "", touch=False, mode="introspect"
    )
    state = await memory_service.get_or_create_state(db, character.id)
    provider, model_cfg = await _resolve_llm(db, character)
    parsed = await monologue.generate(
        provider, model_cfg, ctx["system"], _time_note(state, run.started_at)
    )
    content = str(parsed.get("monologue") or "").strip()
    if not content:
        raise RuntimeError("独白生成失败（空输出）")

    memory = Memory(
        character_id=character.id,
        conversation_id=conv_id or None,
        layer="L4",
        kind="monologue",
        content=content,
        importance=5.0,
        visibility="private",
        meta_json=json.dumps({"source": "heartbeat", "run_id": run.id}, ensure_ascii=False),
    )
    db.add(memory)
    await db.flush()
    run.memory_id = memory.id
    run.output = content
    run.tokens = estimate_tokens(content)
    _apply_state(state, parsed)
    await db.commit()


async def _run_proactive(db, character: Character, conversation: Conversation | None, run: HeartbeatRun) -> None:
    """主动消息：默认最近活跃会话（无则新建），消息与记忆任务同事务落库（复用 enqueue_ingest）"""
    if conversation is None:
        conversation = await get_or_create_conversation(db, character.id)
        run.conversation_id = conversation.id
    ctx = await memory_service.assemble_context(
        db, character, conversation.id, "", touch=True, mode="proactive"
    )
    state = await memory_service.get_or_create_state(db, character.id)
    provider, model_cfg = await _resolve_llm(db, character)
    parsed = await proactive.generate(
        provider, model_cfg, ctx["system"], _time_note(state, run.started_at)
    )
    content = str(parsed.get("message") or "").strip()
    if not content:
        raise RuntimeError("主动消息生成失败（空输出）")

    message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=content,
        meta_json=json.dumps({"source": "heartbeat", "run_id": run.id}, ensure_ascii=False),
    )
    db.add(message)
    await db.flush()
    # source_start_id=0：无用户侧；与消息同事务入队，worker 按角色输出抽取记忆
    memory_service.enqueue_ingest(db, character.id, conversation.id, 0, message.id)
    run.message_id = message.id
    run.output = content
    run.tokens = estimate_tokens(content)
    conversation.updated_at = datetime.now()
    _apply_state(state, parsed)
    await db.commit()


async def run_heartbeat(
    db, job: HeartbeatJob, run_type: str = "monologue", *, manual: bool = False
) -> HeartbeatRun:
    """执行一次心跳：生成 → 落库（记忆/状态）→ 记录 HeartbeatRun。

    生成失败不抛出，写入 status=failed 的运行记录，由调度层决定退避。
    手动试跑（API /run，manual=True）直接调用本函数，不改动调度时间。
    """
    if run_type not in SUPPORTED_TYPES:
        raise ValueError(f"不支持的心跳类型：{run_type}")
    character = await db.get(Character, job.character_id)
    run = HeartbeatRun(
        character_id=job.character_id,
        type=run_type,
        status="running",
        is_manual=manual,
        started_at=datetime.now(),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    if character is None:
        run.status = "failed"
        run.error = "角色不存在"
        run.finished_at = datetime.now()
        await db.commit()
        await db.refresh(run)
        return run

    conversation = await _latest_conversation(db, character.id)
    run.conversation_id = conversation.id if conversation is not None else None
    try:
        if run_type == "monologue":
            await _run_monologue(db, character, conversation, run)
        elif run_type == "proactive":
            await _run_proactive(db, character, conversation, run)
        run.status = "done"
    except Exception as e:  # noqa: BLE001 单次失败不影响调度
        run.status = "failed"
        run.error = str(e)[:500]
        logger.warning("心跳(%s) #%s 失败：%s", run_type, run.id, e)
    run.finished_at = datetime.now()
    await db.commit()
    await db.refresh(run)
    if run.status == "done":
        await db.commit()  # 结束读事务，避免 QQ 投递的新会话写入与 SQLite 读锁互相等待
        await _broadcast(run)
        if run.type == "proactive":
            # 若该会话绑定了 QQ 群且开启主动消息，则同步投递到群聊（失败不影响心跳）
            try:
                from .qq_service import dispatch_proactive

                await dispatch_proactive(
                    character_id=run.character_id,
                    conversation_id=run.conversation_id,
                    text=run.output,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("心跳主动消息投递 QQ 失败（run #%s）：%s", run.id, e)
    return run


async def _broadcast(run: HeartbeatRun) -> None:
    """推送心跳事件（在线用户实时收到；离线用户经 messages 历史回放）"""
    try:
        if run.type == "proactive":
            await ws_service.broadcast_heartbeat(
                character_id=run.character_id,
                conversation_id=run.conversation_id,
                run_id=run.id,
                run_type=run.type,
                message=run.output,
            )
        elif run.type == "monologue":
            await ws_service.broadcast_heartbeat(
                character_id=run.character_id,
                conversation_id=run.conversation_id,
                run_id=run.id,
                run_type=run.type,
                monologue=run.output,
            )
    except Exception as e:  # noqa: BLE001 广播失败不影响心跳结果
        logger.warning("心跳事件广播失败（run #%s）：%s", run.id, e)


async def list_runs(db, character_id: int, limit: int = 20) -> list[HeartbeatRun]:
    result = await db.execute(
        select(HeartbeatRun)
        .where(HeartbeatRun.character_id == character_id)
        .order_by(HeartbeatRun.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


def run_dict(run: HeartbeatRun) -> dict:
    return {
        "id": run.id,
        "character_id": run.character_id,
        "conversation_id": run.conversation_id,
        "type": run.type,
        "status": run.status,
        "is_manual": run.is_manual,
        "output": run.output,
        "memory_id": run.memory_id,
        "message_id": run.message_id,
        "tokens": run.tokens,
        "error": run.error,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


# ---- outbox worker（与记忆/知识库 worker 同模式，独立轮询）----


async def reset_running_jobs() -> int:
    """启动时回收上次进程残留的 running 执行记录（崩溃恢复，at-least-once）"""
    async with SessionLocal() as db:
        result = await db.execute(select(HeartbeatRun).where(HeartbeatRun.status == "running"))
        runs = list(result.scalars().all())
        for run in runs:
            run.status = "failed"
            run.error = "进程中断"
            run.finished_at = datetime.now()
        if runs:
            await db.commit()
        return len(runs)


async def _consecutive_failures(db, character_id: int, limit: int = 10) -> int:
    """最近连续失败次数（最新在前，遇非失败即停）"""
    result = await db.execute(
        select(HeartbeatRun)
        .where(HeartbeatRun.character_id == character_id)
        .order_by(HeartbeatRun.id.desc())
        .limit(limit)
    )
    count = 0
    for run in result.scalars().all():
        if run.status != "failed":
            break
        count += 1
    return count


async def _schedule_after(db, job: HeartbeatJob, run: HeartbeatRun | None) -> None:
    """运行结束后的排程：失败短退避（上限后回到正常节奏），成功按间隔前进"""
    now = datetime.now()
    job.last_run_at = now
    if run is not None and run.status == "failed":
        failures = await _consecutive_failures(db, job.character_id)
        if failures < settings.heartbeat_job_max_attempts:
            job.next_run_at = now + timedelta(seconds=5 * max(failures, 1))
            return
    job.next_run_at = compute_next_run_at(job, now)


async def _run_job(db, job: HeartbeatJob, run_type: str) -> HeartbeatRun:
    return await run_heartbeat(db, job, run_type)


async def run_worker_once(processor=None) -> bool:
    """处理一条到期心跳；返回是否触及调度（供 worker 循环与测试复用）"""
    async with SessionLocal() as db:
        jobs = await due_jobs(db)
        if not jobs:
            return False
        job = jobs[0]
        try:
            run_type = await choose_type(db, job)
            if run_type is None:  # 无满足条件的类型（如仅 proactive 且用户刚说过话），按节奏跳过
                job.last_run_at = datetime.now()
                job.next_run_at = compute_next_run_at(job, job.last_run_at)
            else:
                handle = processor or _run_job
                run = await handle(db, job, run_type)
                await _schedule_after(db, job, run)
        except Exception as e:  # noqa: BLE001 单任务失败不拖垮 worker
            logger.warning("心跳调度 #%s 处理异常：%s", job.character_id, e)
            job.last_run_at = datetime.now()
            job.next_run_at = compute_next_run_at(job, job.last_run_at)
        await db.commit()
        return True


async def worker_loop() -> None:
    while True:
        try:
            processed = await run_worker_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("心跳 worker 异常：%s", e)
            processed = False
        if not processed:
            await asyncio.sleep(settings.heartbeat_worker_interval)


async def start_worker() -> asyncio.Task | None:
    if not settings.heartbeat_enabled:
        return None
    await reset_running_jobs()
    return asyncio.create_task(worker_loop())


async def stop_worker(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task
