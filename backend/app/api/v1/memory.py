import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import Character, CharacterState, Memory
from ...db.session import get_db
from ...schemas.memory import MemoryCreate, MemoryUpdate
from ...services import memory_service

router = APIRouter(prefix="/memory", tags=["memory"])


def _to_out(m: Memory) -> dict:
    return {
        "id": m.id,
        "character_id": m.character_id,
        "conversation_id": m.conversation_id,
        "layer": m.layer,
        "kind": m.kind,
        "content": m.content,
        "importance": m.importance,
        "visibility": m.visibility,
        "access_count": m.access_count,
        "meta": json.loads(m.meta_json or "{}"),
        "created_at": m.created_at,
    }


def _state_to_out(s: CharacterState) -> dict:
    return {
        "character_id": s.character_id,
        "mood": s.mood,
        "arousal": s.arousal,
        "current_focus": s.current_focus,
        "relationship": json.loads(s.relationship_json or "{}"),
        "last_user_at": s.last_user_at,
        "last_beat_at": s.last_beat_at,
        "updated_at": s.updated_at,
    }


@router.get("/characters/{character_id}/memories")
async def list_memories(
    character_id: int,
    layer: str | None = None,
    kind: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    memories = await memory_service.list_memories(db, character_id, layer=layer, kind=kind)
    return [_to_out(m) for m in memories]


@router.post("/characters/{character_id}/memories")
async def create_memory(
    character_id: int,
    payload: MemoryCreate,
    db: AsyncSession = Depends(get_db),
):
    if await db.get(Character, character_id) is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    memory = await memory_service.create_memory(db, character_id, payload)
    return _to_out(memory)


@router.patch("/memories/{memory_id}")
async def update_memory(
    memory_id: int,
    payload: MemoryUpdate,
    db: AsyncSession = Depends(get_db),
):
    memory = await db.get(Memory, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="记忆不存在")
    memory = await memory_service.update_memory(db, memory, payload)
    return _to_out(memory)


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: int, db: AsyncSession = Depends(get_db)):
    memory = await db.get(Memory, memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail="记忆不存在")
    await memory_service.delete_memory(db, memory)
    return {"ok": True}


@router.get("/characters/{character_id}/state")
async def get_state(character_id: int, db: AsyncSession = Depends(get_db)):
    if await db.get(Character, character_id) is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    state = await memory_service.get_or_create_state(db, character_id)
    return _state_to_out(state)
