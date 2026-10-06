import asyncio
import json

from sqlalchemy import select

from .config import ROOT_DIR, settings
from .db.models import Character, ProviderConfig
from .db.session import SessionLocal, init_db


async def seed_defaults() -> None:
    """幂等种子 + 补强：
    - providers/characters 表为空时创建默认 deepseek provider 与影子角色卡
    - 修复角色卡 ext.model.provider 对已删除 provider 的悬空引用（置空改走全局默认）
    - 无默认 provider 时兜底设首个为默认（openai_compat 且 key 为空则补 .env key，不覆盖已有 key）
    """
    async with SessionLocal() as db:
        await _ensure_default_provider(db)
        await _ensure_seed_character(db)
        await _repair_dangling_provider_refs(db)
        await _ensure_default_provider_flag(db)
        await db.commit()


async def _ensure_default_provider(db) -> None:
    """表空时创建默认 deepseek provider"""
    has = (await db.execute(select(ProviderConfig).limit(1))).scalar_one_or_none()
    if has is not None:
        return
    db.add(
        ProviderConfig(
            name="deepseek",
            type="openai_compat",
            base_url=settings.base_url,
            api_key=settings.deepseek_api_key,
            models_json=json.dumps([settings.default_model]),
            is_default=True,
        )
    )
    await db.flush()


async def _ensure_seed_character(db) -> None:
    """表空时创建影子角色卡，ext.model.provider 指向默认 provider"""
    has = (await db.execute(select(Character).limit(1))).scalar_one_or_none()
    if has is not None:
        return
    prompt_path = ROOT_DIR / "prompts" / "phantasm_v1.txt"
    system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
    default_provider = (
        await db.execute(select(ProviderConfig).where(ProviderConfig.is_default.is_(True)).limit(1))
    ).scalar_one_or_none()
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
    if default_provider is not None:
        ext = {
            "model": {
                "provider": default_provider.id,
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


async def _repair_dangling_provider_refs(db) -> None:
    """角色卡 ext.model.provider 指向不存在的 provider → 移除引用，改走全局默认"""
    chars = (await db.execute(select(Character))).scalars().all()
    for char in chars:
        ext = char.ext
        model = ext.get("model") if isinstance(ext.get("model"), dict) else None
        if not model or not model.get("provider"):
            continue
        provider = await db.get(ProviderConfig, int(model["provider"]))
        if provider is None:
            model.pop("provider", None)
            char.ext_json = json.dumps(ext, ensure_ascii=False)


async def _ensure_default_provider_flag(db) -> None:
    """没有默认 provider 时，把首个 provider 设为默认；
    默认 provider 为 openai_compat 且 key 为空时补 .env key（不覆盖已有 key）"""
    default = (
        await db.execute(select(ProviderConfig).where(ProviderConfig.is_default.is_(True)).limit(1))
    ).scalar_one_or_none()
    if default is None:
        first = (
            await db.execute(select(ProviderConfig).order_by(ProviderConfig.id).limit(1))
        ).scalar_one_or_none()
        if first is None:
            return
        first.is_default = True
        default = first
    if default.type == "openai_compat" and not default.api_key and settings.deepseek_api_key:
        default.api_key = settings.deepseek_api_key


async def _seed() -> None:
    await init_db()
    await seed_defaults()
    print("种子数据写入完成")


def main() -> None:
    asyncio.run(_seed())


if __name__ == "__main__":
    main()