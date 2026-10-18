"""心跳调度与内心独白（P3a）专项测试。

用法（仓库根目录）：
    python backend/tests/test_heartbeat.py

退出码：0 = 全部通过；1 = 存在失败。
使用独立临时 SQLite，不调用真实 LLM（用 FakeProvider 注入 resolver）。
"""
import asyncio
import json
import os
import sys
import tempfile
import traceback
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_tmp = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(Path(_tmp.name) / 'heartbeat.db').as_posix()}"

try:
    from sqlalchemy import select  # noqa: E402

    from app.config import settings  # noqa: E402
    from app.db.models import (  # noqa: E402
        Character,
        Conversation,
        HeartbeatRun,
        KbLore,
        Memory,
        Message,
    )
    from app.db.session import SessionLocal, engine, init_db  # noqa: E402
    from app.schemas.heartbeat import HeartbeatConfigUpdate  # noqa: E402
    from app.seed import seed_defaults  # noqa: E402
    from app.services import heartbeat_service, memory_service  # noqa: E402
except Exception:
    traceback.print_exc()
    sys.exit(1)

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"[PASS] {name}")
    else:
        FAILED += 1
        print(f"[FAIL] {name}  {detail}")


class FakeProvider:
    """最小 chat 接口实现：按需产出独白 JSON / 纯文本 / 抛错，并记录入参"""

    def __init__(self, output: str | None = None, fail: bool = False) -> None:
        self.output = output if output is not None else json.dumps(
            {"monologue": "假独白", "mood": "平静", "current_focus": "发呆", "arousal": 0.2},
            ensure_ascii=False,
        )
        self.fail = fail
        self.calls: list[list[dict]] = []

    async def chat(self, messages, *, model, temperature, max_tokens):
        self.calls.append(messages)
        if self.fail:
            raise RuntimeError("llm boom")
        for ch in self.output:
            yield ch


def use_provider(provider: FakeProvider) -> None:
    async def resolver(db, character):
        return provider, {"model": "fake"}

    heartbeat_service.set_resolver(resolver)


async def new_character(db, name: str, ext: dict | None = None) -> Character:
    char = Character(
        name=name,
        card_json=json.dumps({"name": name, "system_prompt": f"你是{name}"}, ensure_ascii=False),
        ext_json=json.dumps(ext or {}, ensure_ascii=False),
    )
    db.add(char)
    await db.commit()
    await db.refresh(char)
    return char


async def new_conversation(db, character_id: int, title: str) -> Conversation:
    conv = Conversation(character_id=character_id, title=title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def test_defaults_and_ext_override(db) -> None:
    char = await new_character(db, "心跳默认")
    job = await heartbeat_service.get_or_create_job(db, char)
    check("默认关闭", job.enabled is False, f"enabled={job.enabled}")
    check(
        "默认间隔/类型/静默取全局",
        job.interval_min == settings.heartbeat_interval_min
        and job.types == ["monologue"]
        and job.quiet_hours.get("start") == settings.heartbeat_quiet_start,
        f"interval={job.interval_min} types={job.types} quiet={job.quiet_hours}",
    )
    check(
        "next_run_at 初始在将来",
        job.next_run_at > datetime.now(),
        f"next={job.next_run_at}",
    )

    char2 = await new_character(
        db,
        "心跳覆盖",
        ext={"heartbeat": {"enabled": True, "interval_min": 30, "daily_limit": 3}},
    )
    job2 = await heartbeat_service.get_or_create_job(db, char2)
    check(
        "ext.heartbeat 覆盖全局",
        job2.enabled is True and job2.interval_min == 30 and job2.daily_limit == 3,
        f"enabled={job2.enabled} interval={job2.interval_min} limit={job2.daily_limit}",
    )


async def test_due_gating(db) -> None:
    now = datetime.now()
    char = await new_character(db, "调度判定")
    job = await heartbeat_service.get_or_create_job(db, char)
    job.enabled = True
    job.jitter_ratio = 0.0
    job.quiet_hours_json = "{}"
    job.next_run_at = now - timedelta(minutes=1)
    await db.commit()

    due = await heartbeat_service.due_jobs(db)
    check("到期且开启 → 可运行", char.id in {j.character_id for j in due}, f"due={[j.character_id for j in due]}")

    job.next_run_at = now + timedelta(minutes=10)
    await db.commit()
    check(
        "未到期 → 不运行",
        char.id not in {j.character_id for j in await heartbeat_service.due_jobs(db)},
    )

    job.enabled = False
    job.next_run_at = now - timedelta(minutes=1)
    await db.commit()
    check(
        "禁用 → 不运行",
        char.id not in {j.character_id for j in await heartbeat_service.due_jobs(db)},
    )

    # 静默时段（跨午夜 23:00-08:00）
    job.enabled = True
    job.quiet_hours_json = json.dumps({"start": "23:00", "end": "08:00"})
    job.next_run_at = datetime(2026, 1, 1, 0, 30)
    await db.commit()
    ids = lambda due: {j.character_id for j in due}  # noqa: E731
    check(
        "跨午夜静默内（01:00）→ 不运行",
        char.id not in ids(await heartbeat_service.due_jobs(db, now=datetime(2026, 1, 1, 1, 0))),
    )
    check(
        "静默外（12:00）→ 运行",
        char.id in ids(await heartbeat_service.due_jobs(db, now=datetime(2026, 1, 1, 12, 0))),
    )
    check(
        "静默开始边界（23:30）→ 不运行",
        char.id not in ids(await heartbeat_service.due_jobs(db, now=datetime(2026, 1, 1, 23, 30))),
    )
    check(
        "静默结束边界（08:00）→ 运行",
        char.id in ids(await heartbeat_service.due_jobs(db, now=datetime(2026, 1, 1, 8, 0))),
    )

    # 每日上限：0 → 永不运行；已达上限 → 不运行
    job.quiet_hours_json = "{}"
    job.daily_limit = 0
    job.next_run_at = now - timedelta(minutes=1)
    await db.commit()
    check(
        "每日上限 0 → 不运行",
        char.id not in {j.character_id for j in await heartbeat_service.due_jobs(db)},
    )

    job.daily_limit = 1
    await db.commit()
    db.add(
        HeartbeatRun(
            character_id=char.id, type="monologue", status="done", started_at=datetime.now()
        )
    )
    await db.commit()
    check(
        "达到每日上限 → 不运行",
        char.id not in {j.character_id for j in await heartbeat_service.due_jobs(db)},
    )

    # 清理，避免影响后续 worker 用例
    job.enabled = False
    job.next_run_at = now + timedelta(hours=1)
    await db.commit()


async def test_next_run_jitter(db) -> None:
    char = await new_character(db, "抖动")
    job = await heartbeat_service.get_or_create_job(db, char)
    job.interval_min = 60
    job.jitter_ratio = 0.0

    now = datetime.now()
    exact = heartbeat_service.compute_next_run_at(job, now)
    check("抖动 0 → 精确间隔", exact - now == timedelta(minutes=60), f"delta={exact - now}")

    job.jitter_ratio = 0.2
    for _ in range(20):
        delta = heartbeat_service.compute_next_run_at(job, now) - now
        if not timedelta(minutes=48) <= delta <= timedelta(minutes=72):
            check("抖动 0.2 → 在 ±20% 区间内", False, f"delta={delta}")
            return
    check("抖动 0.2 → 在 ±20% 区间内", True)


async def test_introspect_context(db) -> None:
    char = await new_character(db, "独白上下文")
    conv = await new_conversation(db, char.id, "独白会话")
    db.add(Message(conversation_id=conv.id, role="user", content="绝密用户原文内容"))
    db.add(
        Memory(
            character_id=char.id,
            layer="L4",
            kind="monologue",
            content="内心独白内容A",
            importance=5.0,
            visibility="private",
        )
    )
    db.add(
        Memory(
            character_id=char.id,
            layer="L3",
            kind="fact",
            content="高重要度事实B",
            importance=9.0,
            visibility="public",
        )
    )
    db.add(
        Memory(
            character_id=char.id,
            layer="L3",
            kind="fact",
            content="低重要度琐事C",
            importance=3.0,
            visibility="public",
        )
    )
    db.add(
        KbLore(
            character_id=char.id,
            keys_json="[]",
            content="世界观常驻设定D",
            constant=True,
            scope="world",
            visibility="public",
            enabled=True,
        )
    )
    db.add(
        KbLore(
            character_id=char.id,
            keys_json="[]",
            content="关系秘密设定E",
            constant=True,
            scope="relation",
            visibility="public",
            enabled=True,
        )
    )
    state = await memory_service.get_or_create_state(db, char.id)
    state.mood = "好奇"
    await db.commit()

    ctx = await memory_service.assemble_context(
        db, char, conv.id, "", touch=False, mode="introspect"
    )
    system = ctx["system"]
    check("introspect 含内心状态", "好奇" in system, system[:200])
    check("introspect 含 L4 private 独白", "内心独白内容A" in system)
    check("introspect 含高重要度 L3", "高重要度事实B" in system)
    check("introspect 排除低重要度 L3", "低重要度琐事C" not in system)
    check("introspect 不含 L1 用户原文", "绝密用户原文内容" not in system)
    check("introspect 含 world 常驻知识", "世界观常驻设定D" in system)
    check("introspect 排除 relation 知识", "关系秘密设定E" not in system)
    check("introspect 无历史记录", ctx["history"] == [])
    check("introspect 独立预算", ctx["budget"] == settings.heartbeat_budget_tokens, f"{ctx['budget']}")

    chat_ctx = await memory_service.assemble_context(db, char, conv.id, "在吗", touch=False)
    check("聊天上下文不含 private 独白", "内心独白内容A" not in chat_ctx["system"])


async def test_monologue_run(db) -> None:
    char = await new_character(db, "独白执行")
    conv = await new_conversation(db, char.id, "独白执行会话")
    db.add(Message(conversation_id=conv.id, role="user", content="你好呀"))
    state = await memory_service.get_or_create_state(db, char.id)
    state.last_user_at = datetime.now() - timedelta(hours=3)
    await db.commit()

    job = await heartbeat_service.get_or_create_job(db, char)
    job = await heartbeat_service.update_job(
        db, char, job, HeartbeatConfigUpdate(enabled=True, interval_min=60, jitter_ratio=0.0)
    )
    check(
        "启用后重排 next_run_at",
        job.enabled is True and job.next_run_at > datetime.now(),
        f"next={job.next_run_at}",
    )
    check(
        "配置回写 ext.heartbeat",
        char.ext.get("heartbeat", {}).get("enabled") is True,
        f"ext={char.ext.get('heartbeat')}",
    )

    fake = FakeProvider(
        json.dumps(
            {
                "monologue": "今天的终端好像有点安静，我发了会呆。",
                "mood": "安静",
                "current_focus": "等用户回来",
                "arousal": 0.6,
            },
            ensure_ascii=False,
        )
    )
    use_provider(fake)
    schedule_before = job.next_run_at
    run = await heartbeat_service.run_heartbeat(db, job, "monologue")

    check("独白执行成功", run.status == "done" and run.error == "", f"status={run.status} err={run.error}")
    check(
        "输出与 token 已记录",
        run.output.startswith("今天的终端") and run.tokens > 0,
        f"output={run.output[:20]} tokens={run.tokens}",
    )
    memory = await db.get(Memory, run.memory_id or 0)
    check(
        "独白落 L4 monologue private",
        memory is not None
        and (memory.layer, memory.kind, memory.visibility) == ("L4", "monologue", "private"),
        f"memory={memory}",
    )
    check(
        "独白关联 run 与最近会话",
        memory is not None
        and memory.conversation_id == conv.id
        and json.loads(memory.meta_json).get("run_id") == run.id,
        f"conv={memory.conversation_id if memory else None}",
    )
    check("run 指向最近会话", run.conversation_id == conv.id, f"conv={run.conversation_id}")

    state = await memory_service.get_or_create_state(db, char.id)
    check(
        "内心状态更新（mood/focus/arousal/last_beat_at）",
        state.mood == "安静"
        and state.current_focus == "等用户回来"
        and abs((state.arousal or 0.0) - 0.6) < 1e-6
        and state.last_beat_at is not None,
        f"mood={state.mood} focus={state.current_focus} arousal={state.arousal}",
    )
    check("手动执行不改动排程", job.next_run_at == schedule_before, f"next={job.next_run_at}")

    messages = fake.calls[-1]
    check("系统提示包含独白指令", "内心独白" in messages[0]["content"])
    check("系统提示包含 introspect 区块", "[角色卡]" in messages[0]["content"])
    check(
        "时间差素材含小时数",
        "距离上次与用户对话已经约 3 小时" in messages[-1]["content"],
        messages[-1]["content"],
    )


async def test_plain_text_fallback(db) -> None:
    char = await new_character(db, "回退解析")
    conv = await new_conversation(db, char.id, "回退解析会话")
    state = await memory_service.get_or_create_state(db, char.id)
    state.mood = "原有心情"
    await db.commit()
    job = await heartbeat_service.get_or_create_job(db, char)
    use_provider(FakeProvider("今天有点想唱歌。"))
    run = await heartbeat_service.run_heartbeat(db, job, "monologue")
    memory = await db.get(Memory, run.memory_id or 0)
    check(
        "非 JSON 输出回退为纯文本独白",
        run.status == "done" and memory is not None and memory.content == "今天有点想唱歌。",
        f"status={run.status} content={memory.content if memory else None}",
    )
    state = await memory_service.get_or_create_state(db, char.id)
    check("回退不影响已有心情", state.mood == "原有心情", f"mood={state.mood}")


async def test_worker_backoff(db) -> None:
    char = await new_character(db, "退避与上限")
    job = await heartbeat_service.get_or_create_job(db, char)
    job.enabled = True
    job.interval_min = 60
    job.jitter_ratio = 0.0
    job.quiet_hours_json = "{}"
    job.next_run_at = datetime.now() - timedelta(minutes=1)
    await db.commit()

    use_provider(FakeProvider(fail=True))
    processed = await heartbeat_service.run_worker_once()
    await db.refresh(job)
    check("worker 消费到期心跳", processed is True)
    runs = await heartbeat_service.list_runs(db, char.id)
    check(
        "失败写入 run 记录",
        len(runs) == 1 and runs[0].status == "failed" and "boom" in runs[0].error,
        f"runs={[(r.status, r.error) for r in runs]}",
    )
    check(
        "首次失败短退避（5s）",
        job.next_run_at - job.last_run_at == timedelta(seconds=5),
        f"delta={job.next_run_at - job.last_run_at if job.last_run_at else None}",
    )

    job.next_run_at = datetime.now() - timedelta(minutes=1)
    await db.commit()
    await heartbeat_service.run_worker_once()
    await db.refresh(job)
    check(
        "连续失败达上限 → 回到正常节奏",
        job.next_run_at - job.last_run_at == timedelta(minutes=60),
        f"delta={job.next_run_at - job.last_run_at if job.last_run_at else None}",
    )

    job.next_run_at = datetime.now() - timedelta(minutes=1)
    await db.commit()
    use_provider(FakeProvider())
    await heartbeat_service.run_worker_once()
    await db.refresh(job)
    runs = await heartbeat_service.list_runs(db, char.id)
    check(
        "恢复成功按间隔前进",
        runs[0].status == "done"
        and job.next_run_at - job.last_run_at == timedelta(minutes=60),
        f"status={runs[0].status}",
    )
    job_info = await heartbeat_service.job_dict(db, job)
    check("job_dict 统计今日执行数", job_info["today_count"] == 3, f"count={job_info['today_count']}")

    # 无到期任务时返回 False（其余用例的调度均已清理/在未来）
    job.enabled = False
    await db.commit()
    check("无待办返回 False", await heartbeat_service.run_worker_once() is False)


async def test_reset_running(db) -> None:
    char = await new_character(db, "崩溃回收")
    run = HeartbeatRun(character_id=char.id, type="monologue", status="running")
    db.add(run)
    await db.commit()
    run_id = run.id

    recycled = await heartbeat_service.reset_running_jobs()
    check("启动回收 running 记录", recycled >= 1, f"recycled={recycled}")
    async with SessionLocal() as fresh:
        row = await fresh.get(HeartbeatRun, run_id)
        check(
            "回收后置 failed 且标注进程中断",
            row is not None and row.status == "failed" and row.error == "进程中断",
            f"status={row.status if row else None}",
        )


async def test_manual_run_unsupported(db) -> None:
    char = await new_character(db, "类型校验")
    job = await heartbeat_service.get_or_create_job(db, char)
    try:
        await heartbeat_service.run_heartbeat(db, job, "bogus")
        check("非支持类型直接拒绝", False, "未抛出 ValueError")
    except ValueError:
        check("非支持类型直接拒绝", True)


async def run() -> None:
    await init_db()
    await seed_defaults()
    async with SessionLocal() as db:
        await test_defaults_and_ext_override(db)
        await test_due_gating(db)
        await test_next_run_jitter(db)
        await test_introspect_context(db)
        await test_monologue_run(db)
        await test_plain_text_fallback(db)
        await test_worker_backoff(db)
        await test_reset_running(db)
        await test_manual_run_unsupported(db)

    await engine.dispose()
    try:
        _tmp.cleanup()
    except Exception:
        pass
    print(f"\n结果：{PASSED} 通过 / {FAILED} 失败")
    sys.exit(1 if FAILED else 0)


def main() -> None:
    try:
        asyncio.run(run())
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
