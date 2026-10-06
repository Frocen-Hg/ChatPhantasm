import asyncio

from sqlalchemy import select

from .db.models import Character
from .db.session import SessionLocal, init_db
from .services import chat_service


async def _main() -> None:
    await init_db()
    async with SessionLocal() as db:
        chars = (await db.execute(select(Character).order_by(Character.id))).scalars().all()
        if not chars:
            print("（没有角色卡，请先通过 Web 端创建，或运行 python -m app.seed）")
            return

        print("可用角色：")
        for i, c in enumerate(chars):
            print(f"  {i}. {c.name}")
        try:
            idx = int(input("选择角色编号: ").strip())
            character = chars[idx]
        except (ValueError, IndexError):
            print("无效选择")
            return

        provider, model_cfg = await chat_service.resolve_provider(db, character)
        conversation = await chat_service.get_or_create_conversation(db, character.id)
        print(f"\n== 与 {character.name} 对话，输入 exit 退出 ==")

        while True:
            text = input("\n[你] > ").strip()
            if text.lower() in ("exit", "quit"):
                break
            if not text:
                continue
            print(f"\n[{character.name}] ", end="", flush=True)
            try:
                async for token in chat_service.stream_reply(
                    db, conversation, character, provider, model_cfg, text
                ):
                    print(token, end="", flush=True)
                print()
            except Exception as e:  # noqa: BLE001
                print(f"\n（掉线）{e}")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()