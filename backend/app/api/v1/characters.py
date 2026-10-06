import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import Character
from ...db.session import get_db
from ...schemas.character import CharacterCreate, CharacterUpdate
from ...services import character_service

router = APIRouter(prefix="/characters", tags=["characters"])


def _to_out(c: Character) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "schema_version": c.schema_version,
        "card": json.loads(c.card_json or "{}"),
        "ext": json.loads(c.ext_json or "{}"),
        "avatar": c.avatar,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


@router.get("")
async def list_characters(db: AsyncSession = Depends(get_db)):
    chars = await character_service.list_characters(db)
    return [_to_out(c) for c in chars]


@router.post("")
async def create_character(payload: CharacterCreate, db: AsyncSession = Depends(get_db)):
    character = await character_service.create_character(db, payload.card, payload.ext)
    return _to_out(character)


@router.get("/{character_id}")
async def get_character(character_id: int, db: AsyncSession = Depends(get_db)):
    character = await db.get(Character, character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return _to_out(character)


@router.put("/{character_id}")
async def update_character(character_id: int, payload: CharacterUpdate, db: AsyncSession = Depends(get_db)):
    character = await db.get(Character, character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    character = await character_service.update_character(db, character, payload.card, payload.ext)
    return _to_out(character)


@router.delete("/{character_id}")
async def delete_character(character_id: int, db: AsyncSession = Depends(get_db)):
    character = await db.get(Character, character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    await character_service.delete_character(db, character)
    return {"ok": True}