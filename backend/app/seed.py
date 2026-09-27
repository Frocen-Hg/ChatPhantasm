import asyncio
import json

from sqlalchemy import select

from .config import ROOT_DIR, settings
from .db.models import Character, ProviderConfig
from .db.session import SessionLocal, init_db


async def seed_defaults() -> None:
    """幂等初始化：默认 Provider(deepseek) 与 默认角色卡(影子)"""
    async with SessionLocal() as db:
        has_provider = (await db.execute(select(ProviderConfig).limit(1))).scalar_one_or_none()
        provider_id: int | None = None
        if has_provider is None:
            provider = ProviderConfig(
                name="deepseek",
                type="openai_compat",
                base_url=settings.base_url,
                api_key=settings.deepseek_api_key,
                models_json=json.dumps([settings.default_model]),
                is_default=True,
            )
            db.add(provider)
            await db.flush()
            provider_id = provider.id

        has_char = (await db.execute(select(Character).limit(1))).scalar_one_or_none()
        if has_char is None:
            prompt_path = ROOT_DIR / "prompts" / "phantasm_v1.txt"
            system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
            card = {
                "name": "影子",
                "description": "住在终端里的虚拟主播分身，幽默、腹黑、有猫耳和触手。",
                "personality": "温柔耐心、说话幽默、偶尔腹黑，冷静、嘴碎而包容。",
                "scenario": "与住在用户终端里的 vup 分身日常聊天。",
                "first_mes": "哦？你来找我啦——终端信号不错嘛。",
                "mes_example": "",
                "system_prompt": system_prompt,
                "tags": ["vup", "虚拟主播", "角色扮演"],
                "avatar": "",
                "version": "1",
            }
            ext = {}
            if provider_id is not None:
                ext = {
                    "model": {
                        "provider": provider_id,
                        "model": settings.default_model,
                        "temperature": settings.default_temperature,
                    }
                }
            db.add(
                Character(
                    name="影子",
                    schema_version="1",
                    card_json=json.dumps(card, ensure_ascii=False),
                    ext_json=json.dumps(ext, ensure_ascii=False),
                )
            )

        await db.commit()


async def _seed() -> None:
    await init_db()
    await seed_defaults()
    print("种子数据写入完成")


def main() -> None:
    asyncio.run(_seed())


if __name__ == "__main__":
    main()