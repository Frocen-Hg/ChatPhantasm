import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import Character, CharacterState, Memory
from ...db.session import get_db
from ...schemas.memory import (
    ContextPreviewRequest,
    MemoryCreate,
    MemorySearchRequest,
    MemoryUpdate,
    StateUpdate,
)
from ...services import memory_service, vector_service

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
        "indexed": m.embedding_id is not None,  # 是否已写入向量索引
        "source_start_id": m.source_start_id,
        "source_end_id": m.source_end_id,
        "decay_at": m.decay_at,
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


@router.patch("/characters/{character_id}/state")
async def update_state(
    character_id: int,
    payload: StateUpdate,
    db: AsyncSession = Depends(get_db),
):
    if await db.get(Character, character_id) is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    state = await memory_service.get_or_create_state(db, character_id)
    state = await memory_service.update_state(db, state, payload)
    return _state_to_out(state)


@router.post("/search")
async def search_memories(payload: MemorySearchRequest, db: AsyncSession = Depends(get_db)):
    """检索预览：只读返回带打分拆解的候选，不更新访问计数、不落库"""
    if await db.get(Character, payload.character_id) is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    results = await memory_service.search_memories(
        db, payload.character_id, payload.query, payload.top_k, payload.half_life_days
    )
    return {"query": payload.query, "results": results}


@router.post("/context-preview")
async def context_preview(payload: ContextPreviewRequest, db: AsyncSession = Depends(get_db)):
    """上下文预览：dry-run 组装 system 各区块与 L1 历史，返回 token 占用（不调 LLM、不落库）"""
    character = await db.get(Character, payload.character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    ctx = await memory_service.assemble_context(
        db, character, payload.conversation_id or 0, payload.query, touch=False
    )
    return ctx


@router.post("/characters/{character_id}/reindex")
async def reindex_memories(character_id: int, db: AsyncSession = Depends(get_db)):
    """重建该角色的记忆向量索引（换嵌入模型或补历史数据后使用）"""
    if await db.get(Character, character_id) is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    available = await vector_service.store_available()
    indexed = await memory_service.reindex_memories(db, character_id)
    return {"indexed": indexed, "available": available}


@router.post("/characters/{character_id}/decay")
async def decay_memories(character_id: int, db: AsyncSession = Depends(get_db)):
    """手动触发惰性衰减归档（平时在摘要触发时同频自动执行）"""
    if await db.get(Character, character_id) is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    archived = await memory_service.decay_memories(db, character_id)
    return {"archived": archived}
