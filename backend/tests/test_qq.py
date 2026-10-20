"""QQ 群聊接入（NapCat / OneBot 11）专项测试。

用法（仓库根目录）：
    python backend/tests/test_qq.py

退出码：0 = 全部通过；1 = 存在失败。
使用独立临时 SQLite，不调用真实 LLM / 不连接 QQ。
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
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(Path(_tmp.name) / 'qq.db').as_posix()}"

try:
    from sqlalchemy import select  # noqa: E402

    from app.db.models import (  # noqa: E402
        Character,
        Conversation,
        Message,
        QqBinding,
        QqMember,
        QqReplyLog,
    )
    from app.db.session import SessionLocal, engine, init_db  # noqa: E402
    from app.services import qq_service  # noqa: E402
    from app.services.qq_service import (  # noqa: E402
        IncomingMessage,
        ParsedEvent,
        choose_trigger,
        parse_event,
        reply_stats,
    )
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


def event(
    *,
    text: str = "你好",
    user_id: str = "10001",
    nickname: str = "小明",
    card: str = "",
    group_id: str = "88888",
    bot_uin: str = "99999",
    mentions: bool = False,
    role: str = "member",
) -> ParsedEvent:
    message = [{"type": "text", "data": {"text": text}}]
    if mentions:
        message.insert(0, {"type": "at", "data": {"qq": bot_uin}})
    payload = {
        "post_type": "message",
        "message_type": "group",
        "self_id": int(bot_uin),
        "group_id": int(group_id),
        "group_name": "测试群",
        "message_id": 123456,
        "user_id": int(user_id),
        "sender": {"user_id": int(user_id), "nickname": nickname, "card": card, "role": role},
        "message": message,
    }
    parsed = parse_event(payload, bot_uin)
    assert parsed is not None
    return parsed


async def new_character(db, name: str = "群聊角色") -> Character:
    char = Character(
        name=name,
        card_json=json.dumps({"name": name, "system_prompt": f"你是{name}"}, ensure_ascii=False),
        ext_json="{}",
    )
    db.add(char)
    await db.commit()
    await db.refresh(char)
    return char


async def new_binding(db, character_id: int, **kwargs) -> QqBinding:
    defaults = {
        "character_id": character_id,
        "bot_uin": "99999",
        "group_id": "88888",
        "group_name": "测试群",
        "enabled": True,
        "reply_mode": "mention",
        "keywords_json": "[]",
        "reply_probability": 0.2,
        "min_interval_sec": 60,
        "max_replies_per_hour": 10,
        "max_replies_per_day": 50,
        "debounce_sec": 30.0,
        "mention_bypass_cooldown": True,
        "proactive_enabled": False,
        "group_note": "",
    }
    defaults.update(kwargs)
    binding = QqBinding(**defaults)
    db.add(binding)
    await db.commit()
    await db.refresh(binding)
    return binding


def test_parse() -> None:
    payload = {
        "post_type": "message",
        "message_type": "group",
        "self_id": 99999,
        "group_id": 88888,
        "group_name": "测试群",
        "message_id": 42,
        "user_id": 10001,
        "sender": {"user_id": 10001, "nickname": "小明", "card": "明仔", "role": "admin"},
        "message": [
            {"type": "at", "data": {"qq": "99999"}},
            {"type": "text", "data": {"text": " 在吗"}},
            {"type": "image", "data": {"file": "abc"}},
            {"type": "reply", "data": {"id": "77"}},
        ],
    }
    parsed = parse_event(payload, "99999")
    check("解析群消息", parsed is not None and parsed.group_id == "88888")
    assert parsed is not None
    check("@ 标记与展示名", parsed.mentions_self and parsed.display_name == "明仔")
    check("图片占位与回复 id", "[图片]" in parsed.text and parsed.reply_to_id == "77")
    check("@ 你标记写入文本", parsed.text.startswith("（@你）"))

    payload["message_id"] = 43
    check("忽略自身消息", parse_event({**payload, "user_id": 99999}, "99999") is None)
    check("忽略私聊", parse_event({**payload, "message_type": "private"}, "99999") is None)

    cq_payload = {
        **payload,
        "message": "[CQ:at,qq=99999] 在吗 [CQ:face,id=1]",
        "message_type": "group",
        "user_id": 10002,
        "sender": {"user_id": 10002, "nickname": "小红"},
    }
    cq = parse_event(cq_payload, "99999")
    check("解析 CQ 字符串", cq is not None and cq.mentions_self and "[表情]" in cq.text)


def test_choose_trigger() -> None:
    now = datetime(2026, 5, 1, 12, 0)
    base = dict(
        reply_mode="mention",
        has_mention=False,
        has_keyword=False,
        probability=0.0,
        random_value=0.99,
        last_reply_at=None,
        now=now,
        min_interval_sec=60,
        mention_bypass_cooldown=True,
        hour_count=0,
        day_count=0,
        max_per_hour=10,
        max_per_day=50,
    )
    trigger, _ = choose_trigger(**{**base, "has_mention": True})
    check("仅 @ 模式：@ 触发", trigger == "mention")
    trigger, reason = choose_trigger(**base)
    check("仅 @ 模式：普通消息不触发", trigger is None and reason == "no_trigger")
    trigger, _ = choose_trigger(**{**base, "reply_mode": "keyword", "has_keyword": True})
    check("关键词模式：命中触发", trigger == "keyword")
    trigger, _ = choose_trigger(
        **{**base, "reply_mode": "ambient", "probability": 0.0}
    )
    check("概率模式：概率 0 不触发", trigger is None)
    trigger, _ = choose_trigger(
        **{**base, "reply_mode": "ambient", "probability": 1.0, "random_value": 0.0}
    )
    check("概率模式：概率 1 触发", trigger == "ambient")
    trigger, _ = choose_trigger(**{**base, "reply_mode": "all"})
    check("全量模式：普通消息触发", trigger == "all")

    trigger, reason = choose_trigger(
        **{
            **base,
            "reply_mode": "mention",
            "has_mention": True,
            "last_reply_at": now - timedelta(seconds=10),
            "mention_bypass_cooldown": True,
        }
    )
    check("被 @ 默认跳过冷却", trigger == "mention")
    trigger, reason = choose_trigger(
        **{
            **base,
            "reply_mode": "mention",
            "has_mention": True,
            "last_reply_at": now - timedelta(seconds=10),
            "mention_bypass_cooldown": False,
        }
    )
    check("@ 冷却生效", trigger is None and reason == "cooldown")
    trigger, reason = choose_trigger(
        **{
            **base,
            "reply_mode": "all",
            "last_reply_at": now - timedelta(seconds=10),
        }
    )
    check("非 @ 冷却生效", trigger is None and reason == "cooldown")
    trigger, reason = choose_trigger(**{**base, "reply_mode": "all", "hour_count": 10})
    check("小时上限拦截", trigger is None and reason == "hourly_limit")
    trigger, reason = choose_trigger(**{**base, "reply_mode": "all", "day_count": 50})
    check("每日上限拦截", trigger is None and reason == "daily_limit")
    trigger, _ = choose_trigger(
        **{**base, "reply_mode": "all", "max_per_hour": 0, "max_per_day": 0, "hour_count": 999}
    )
    check("上限 0 = 不限", trigger == "all")


async def test_db_flow(db) -> None:
    char = await new_character(db)
    binding = await new_binding(db, char.id)

    found = await qq_service.bridge._find_binding(db, "99999", "88888")
    check("按账号+群找到绑定", found is not None and found.id == binding.id)
    wildcard = await new_binding(db, char.id, bot_uin="", group_id="77777")
    found = await qq_service.bridge._find_binding(db, "12345", "77777")
    check("空账号绑定匹配任意账号", found is not None and found.id == wildcard.id)

    parsed = event(text="大家好", mentions=True, card="明仔")
    await qq_service.bridge._handle_incoming(parsed)
    qq_service.bridge.forget_binding(binding.id)

    await db.refresh(binding)
    check("首次消息自动建会话", binding.conversation_id is not None)
    conversation = await db.get(Conversation, binding.conversation_id)
    check(
        "会话标题带群名",
        conversation is not None and "测试群" in conversation.title,
        f"title={getattr(conversation, 'title', None)}",
    )
    rows = list(
        (
            await db.execute(
                select(Message).where(Message.conversation_id == conversation.id)
            )
        )
        .scalars()
        .all()
    )
    check("入站消息落库为 user", len(rows) == 1 and rows[0].role == "user")
    check("消息带发言人前缀", rows[0].content.startswith("【明仔】"))
    meta = json.loads(rows[0].meta_json)
    check("消息 meta 标记来源", meta.get("source") == "qq" and meta.get("group_id") == "88888")

    member = (
        await db.execute(
            select(QqMember).where(
                QqMember.binding_id == binding.id, QqMember.user_id == "10001"
            )
        )
    ).scalar_one_or_none()
    check("成员首次发言自动登记", member is not None and member.message_count == 1)

    member.tags_json = json.dumps(["朋友", "老同学"], ensure_ascii=False)
    member.note = "喜欢抬杠但很可靠"
    await db.commit()
    incoming = IncomingMessage(
        binding_id=binding.id,
        character_id=char.id,
        conversation_id=conversation.id,
        bot_uin="99999",
        group_id="88888",
        db_message_id=rows[0].id,
        message_id="123",
        user_id="10001",
        display_name="明仔",
        text="大家好",
        mentions_self=True,
        replied_to_bot=False,
        received_at=datetime.now(),
    )
    block = await qq_service.bridge._member_block(db, binding, [incoming])
    check(
        "成员标签注入文本",
        "标签：朋友、老同学" in block and "印象：喜欢抬杠但很可靠" in block,
        block,
    )

    member.ignored = True
    await db.commit()
    await qq_service.bridge._handle_incoming(event(text="被忽略的消息", user_id="10001"))
    qq_service.bridge.forget_binding(binding.id)
    count = (
        await db.execute(
            select(Message).where(Message.conversation_id == conversation.id)
        )
    ).scalars().all()
    check("忽略成员不写入上下文", len(count) == 1, f"count={len(count)}")
    await db.refresh(member)
    check("忽略成员仍统计发言数", member.message_count == 2, f"count={member.message_count}")

    # 频率统计
    fixed = datetime(2026, 5, 1, 12, 0)
    db.add_all(
        [
            QqReplyLog(
                binding_id=binding.id,
                character_id=char.id,
                conversation_id=conversation.id,
                user_id="10001",
                trigger="mention",
                content="a",
                created_at=fixed,
            ),
            QqReplyLog(
                binding_id=binding.id,
                character_id=char.id,
                conversation_id=conversation.id,
                user_id="10001",
                trigger="ambient",
                content="b",
                created_at=fixed - timedelta(hours=2),
            ),
            QqReplyLog(
                binding_id=binding.id,
                character_id=char.id,
                conversation_id=conversation.id,
                user_id="10001",
                trigger="ambient",
                content="c",
                created_at=fixed - timedelta(days=1),
            ),
        ]
    )
    await db.commit()
    hour_count, day_count, last = await reply_stats(db, binding.id, fixed + timedelta(minutes=5))
    check(
        "回复统计：1 小时 / 今日 / 最近",
        hour_count == 1 and day_count == 2 and last == fixed,
        f"hour={hour_count} day={day_count} last={last}",
    )

    # 主动消息：未开启 proactive 时不投递（且无需连接）
    sent = await qq_service.dispatch_proactive(
        character_id=char.id, conversation_id=conversation.id, text="主动说一句"
    )
    check("主动消息未开启 → 跳过", sent is False)

    try:
        await qq_service.bridge.send_group(binding, "hello")
        check("未连接时发送应失败", False)
    except RuntimeError as e:
        check("未连接时发送报错", "未连接" in str(e), str(e))


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))

    async def close(self) -> None:
        return None


class FakeProvider:
    def __init__(self, output: str = "你好呀，我在。") -> None:
        self.output = output
        self.calls: list[list[dict]] = []

    async def chat(self, messages, *, model, temperature, max_tokens):
        self.calls.append(messages)
        for char in self.output:
            yield char


async def test_generation_and_send(db) -> None:
    char = await new_character(db, "发送测试角色")
    binding = await new_binding(
        db,
        char.id,
        group_id="66666",
        reply_mode="all",
        min_interval_sec=0,
        max_replies_per_hour=0,
        max_replies_per_day=0,
    )
    conversation = await qq_service.bridge._ensure_conversation(db, binding)
    message = Message(
        conversation_id=conversation.id,
        role="user",
        content="【小红】随便聊聊",
        meta_json=json.dumps({"source": "qq"}),
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    incoming = IncomingMessage(
        binding_id=binding.id,
        character_id=char.id,
        conversation_id=conversation.id,
        bot_uin="99999",
        group_id="66666",
        db_message_id=message.id,
        message_id="1",
        user_id="10002",
        display_name="小红",
        text="随便聊聊",
        mentions_self=False,
        replied_to_bot=False,
        received_at=datetime.now(),
    )

    fake_ws = FakeWebSocket()
    conn = qq_service.OneBotConnection(fake_ws, "99999")
    qq_service.bridge._connections[id(conn)] = conn
    provider = FakeProvider()
    original = qq_service.resolve_provider

    async def resolver(_db, _character):
        return provider, {"model": "fake", "temperature": 0.7, "max_tokens": 200}

    qq_service.resolve_provider = resolver
    try:
        task = asyncio.create_task(qq_service.bridge._process_batch(binding.id, [incoming]))
        for _ in range(200):
            if fake_ws.sent:
                break
            await asyncio.sleep(0.02)
        check("全量模式生成后调用发送 action", bool(fake_ws.sent))
        if fake_ws.sent:
            action = fake_ws.sent[0]
            check(
                "发送 action 为 send_group_msg",
                action.get("action") == "send_group_msg",
                str(action)[:300],
            )
            check(
                "发送内容进入 text 段",
                any(
                    seg.get("type") == "text" and "你好呀" in seg.get("data", {}).get("text", "")
                    for seg in action.get("params", {}).get("message", [])
                ),
                str(action.get("params"))[:300],
            )
            qq_service.bridge.handle_payload(
                conn,
                {
                    "status": "ok",
                    "retcode": 0,
                    "data": {"message_id": 555},
                    "echo": action.get("echo"),
                },
            )
        await asyncio.wait_for(task, timeout=10)
        await db.commit()

        assistant = (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation.id, Message.role == "assistant")
                .order_by(Message.id.desc())
            )
        ).scalars().first()
        check("回复写入会话 assistant 消息", assistant is not None and "你好呀" in assistant.content)
        log = (
            await db.execute(
                select(QqReplyLog).where(QqReplyLog.binding_id == binding.id).order_by(QqReplyLog.id.desc())
            )
        ).scalars().first()
        check(
            "回复记录 trigger=all 且带消息 id",
            log is not None and log.trigger == "all" and log.message_id == assistant.id,
            f"log={getattr(log, 'trigger', None)}",
        )
        check("记录机器人消息 id（用于识别回复）", qq_service.bridge.is_bot_message("555"))
        check("生成请求包含 system 与历史", provider.calls and provider.calls[0][0]["role"] == "system")

        fake_ws.sent.clear()
        groups_task = asyncio.create_task(qq_service.bridge.list_groups("99999"))
        for _ in range(200):
            if fake_ws.sent:
                break
            await asyncio.sleep(0.02)
        check("群列表调用 get_group_list", fake_ws.sent and fake_ws.sent[0].get("action") == "get_group_list")
        if fake_ws.sent:
            qq_service.bridge.handle_payload(
                conn,
                {
                    "status": "ok",
                    "retcode": 0,
                    "data": [{"group_id": 66666, "group_name": "测试群", "member_count": 3}],
                    "echo": fake_ws.sent[0].get("echo"),
                },
            )
        groups = await asyncio.wait_for(groups_task, timeout=10)
        check("群列表解析", groups and groups[0]["group_name"] == "测试群", str(groups))
    finally:
        qq_service.resolve_provider = original
        conn.closed = True
        qq_service.bridge._connections.pop(id(conn), None)


async def test_api(db) -> None:
    import httpx

    from app.main import app

    char = await new_character(db, "API测试角色")
    char_id = char.id
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        status_resp = await client.get("/api/v1/qq/status")
        check("QQ status API", status_resp.status_code == 200 and "connected" in status_resp.json())

        resp = await client.post(
            "/api/v1/qq/bindings",
            json={
                "character_id": char.id,
                "group_id": "55555",
                "group_name": "API 群",
                "reply_mode": "keyword",
                "keywords": ["在吗", "在吗", " hello "],
                "max_replies_per_hour": 3,
            },
        )
        check("创建 QQ 绑定 API", resp.status_code == 201, resp.text)
        binding = resp.json() if resp.status_code == 201 else {}
        check(
            "绑定默认与关键词去重",
            binding.get("character_name") == "API测试角色"
            and binding.get("keywords") == ["在吗", "hello"],
            str(binding)[:300],
        )

        duplicate = await client.post(
            "/api/v1/qq/bindings",
            json={"character_id": char.id, "group_id": "55555"},
        )
        check("重复群绑定 409", duplicate.status_code == 409, duplicate.text)

        resp = await client.patch(
            f"/api/v1/qq/bindings/{binding['id']}",
            json={"reply_mode": "ambient", "reply_probability": 0.35, "enabled": False},
        )
        check(
            "修改绑定配置 API",
            resp.status_code == 200
            and resp.json().get("reply_mode") == "ambient"
            and resp.json().get("enabled") is False,
            resp.text,
        )

        member = QqMember(
            binding_id=binding["id"],
            user_id="10010",
            nickname="API 成员",
            role="admin",
            tags_json="[]",
        )
        db.add(member)
        await db.commit()
        await db.refresh(member)
        resp = await client.patch(
            f"/api/v1/qq/members/{member.id}",
            json={"tags": ["朋友", "同事"], "note": "测试备注", "ignored": True},
        )
        check(
            "修改成员标签 API",
            resp.status_code == 200
            and resp.json().get("tags") == ["朋友", "同事"]
            and resp.json().get("ignored") is True,
            resp.text,
        )

        resp = await client.post(
            f"/api/v1/qq/bindings/{binding['id']}/send", json={"text": "测试"}
        )
        check("未连接发送测试返回 503", resp.status_code == 503, resp.text)

        conversation = Conversation(character_id=char.id, title="待删 QQ 会话")
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        binding_row = await db.get(QqBinding, binding["id"])
        binding_row.conversation_id = conversation.id
        await db.commit()
        resp = await client.delete(f"/api/v1/conversations/{conversation.id}")
        db.expire_all()
        binding_row = await db.get(QqBinding, binding["id"])
        check(
            "删除会话后 QQ 绑定解除引用",
            resp.status_code == 200 and binding_row is not None and binding_row.conversation_id is None,
            resp.text,
        )

        resp = await client.delete(f"/api/v1/qq/bindings/{binding['id']}")
        check("删除绑定 API", resp.status_code == 200)
        left = (
            await db.execute(select(QqMember).where(QqMember.binding_id == binding["id"]))
        ).scalars().all()
        check("删除绑定级联成员", not left)

        await client.delete(f"/api/v1/characters/{char_id}")


async def main() -> None:
    await init_db()
    async with SessionLocal() as db:
        test_parse()
        test_choose_trigger()
        await test_db_flow(db)
        await test_generation_and_send(db)
        await test_api(db)
    await qq_service.bridge.shutdown()
    await engine.dispose()
    try:
        _tmp.cleanup()
    except Exception:
        pass
    print(f"\n结果：{PASSED} 通过 / {FAILED} 失败")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    asyncio.run(main())
