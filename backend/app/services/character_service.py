import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Character

DEFAULT_CARD_VERSION = "1"


def normalize_card(card: dict) -> dict:
    """补全规范角色卡字段，保持卡片字典形态（后续兼容多 Schema 的归一化入口）"""
    return {
        "name": str(card.get("name") or "未命名"),
        "description": str(card.get("description") or ""),
        "personality": str(card.get("personality") or ""),
        "scenario": str(card.get("scenario") or ""),
        "first_mes": str(card.get("first_mes") or ""),
        "mes_example": str(card.get("mes_example") or ""),
        "system_prompt": str(card.get("system_prompt") or ""),
        "tags": list(card.get("tags") or []),
        "avatar": str(card.get("avatar") or ""),
        "version": str(card.get("version") or DEFAULT_CARD_VERSION),
    }


def compose_system_prompt(card: dict) -> str:
    """优先使用角色卡显式 system_prompt，否则由字段拼装"""
    sp = (card.get("system_prompt") or "").strip()
    if sp:
        return sp
    parts = [
        card.get("name", ""),
        card.get("description", ""),
        card.get("personality", ""),
        card.get("scenario", ""),
    ]
    return "\n".join(str(p) for p in parts if str(p).strip())


async def list_characters(db: AsyncSession) -> list[Character]:
    result = await db.execute(select(Character).order_by(Character.created_at))
    return list(result.scalars().all())


async def get_character(db: AsyncSession, character_id: int) -> Character | None:
    return await db.get(Character, character_id)


async def create_character(db: AsyncSession, card: dict, ext: dict | None = None) -> Character:
    normalized = normalize_card(card)
    character = Character(
        name=normalized["name"],
        schema_version=normalized["version"],
        card_json=json.dumps(normalized, ensure_ascii=False),
        ext_json=json.dumps(ext or {}, ensure_ascii=False),
        avatar=normalized.get("avatar") or None,
    )
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character


async def update_character(
    db: AsyncSession,
    character: Character,
    card: dict | None = None,
    ext: dict | None = None,
) -> Character:
    if card is not None:
        normalized = normalize_card(card)
        character.card_json = json.dumps(normalized, ensure_ascii=False)
        character.name = normalized["name"]
        character.schema_version = normalized["version"]
        character.avatar = normalized.get("avatar") or None
    if ext is not None:
        character.ext_json = json.dumps(ext, ensure_ascii=False)
    await db.commit()
    await db.refresh(character)
    return character


async def delete_character(db: AsyncSession, character: Character) -> None:
    await db.delete(character)
    await db.commit()