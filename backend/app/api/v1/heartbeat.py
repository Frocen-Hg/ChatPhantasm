from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import Character
from ...db.session import get_db
from ...schemas.heartbeat import HeartbeatConfigUpdate, HeartbeatRunRequest
from ...services import heartbeat_service

router = APIRouter(prefix="/heartbeat", tags=["heartbeat"])


async def _require_character(db: AsyncSession, character_id: int) -> Character:
    character = await db.get(Character, character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return character


@router.get("/characters/{character_id}")
async def get_config(character_id: int, db: AsyncSession = Depends(get_db)):
    """心跳配置（不存在则按 ext.heartbeat/全局默认物化一行，默认关闭）"""
    character = await _require_character(db, character_id)
    job = await heartbeat_service.get_or_create_job(db, character)
    return await heartbeat_service.job_dict(db, job)


@router.put("/characters/{character_id}")
async def update_config(
    character_id: int,
    payload: HeartbeatConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    character = await _require_character(db, character_id)
    job = await heartbeat_service.get_or_create_job(db, character)
    try:
        job = await heartbeat_service.update_job(db, character, job, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await heartbeat_service.job_dict(db, job)


@router.post("/characters/{character_id}/run")
async def run_once(
    character_id: int,
    payload: HeartbeatRunRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """手动触发一次心跳（试跑）：绕过开关/静默/上限，不改动调度时间"""
    character = await _require_character(db, character_id)
    job = await heartbeat_service.get_or_create_job(db, character)
    run_type = payload.type if payload is not None else "monologue"
    try:
        run = await heartbeat_service.run_heartbeat(db, job, run_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return heartbeat_service.run_dict(run)


@router.get("/characters/{character_id}/runs")
async def list_runs(
    character_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    await _require_character(db, character_id)
    runs = await heartbeat_service.list_runs(db, character_id, max(1, min(limit, 100)))
    return [heartbeat_service.run_dict(r) for r in runs]
