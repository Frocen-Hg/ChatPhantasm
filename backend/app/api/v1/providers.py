import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import ProviderConfig
from ...db.session import get_db
from ...schemas.provider import ProviderCreate, ProviderTest, ProviderUpdate
from ...services.provider_service import build_provider

router = APIRouter(prefix="/providers", tags=["providers"])


def _mask_key(key: str | None) -> str:
    if not key:
        return ""
    return key[:4] + "****" if len(key) > 8 else "****"


def _to_out(p: ProviderConfig) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "type": p.type,
        "base_url": p.base_url,
        "models": p.models,
        "is_default": p.is_default,
        "api_key_masked": _mask_key(p.api_key),
    }


async def _clear_default(db: AsyncSession) -> None:
    result = await db.execute(select(ProviderConfig).where(ProviderConfig.is_default.is_(True)))
    for p in result.scalars().all():
        p.is_default = False


@router.get("")
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProviderConfig).order_by(ProviderConfig.id))
    return [_to_out(p) for p in result.scalars().all()]


@router.post("")
async def create_provider(payload: ProviderCreate, db: AsyncSession = Depends(get_db)):
    if payload.is_default:
        await _clear_default(db)
    p = ProviderConfig(
        name=payload.name,
        type=payload.type,
        base_url=payload.base_url,
        api_key=payload.api_key,
        models_json=json.dumps(payload.models),
        is_default=payload.is_default,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _to_out(p)


@router.put("/{provider_id}")
async def update_provider(provider_id: int, payload: ProviderUpdate, db: AsyncSession = Depends(get_db)):
    p = await db.get(ProviderConfig, provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Provider 不存在")

    if payload.is_default:
        await _clear_default(db)
        p.is_default = True
    elif payload.is_default is False and p.is_default:
        # 显式取消默认，但避免误伤：简单置为 False
        p.is_default = False

    if payload.name is not None:
        p.name = payload.name
    if payload.type is not None:
        p.type = payload.type
    if payload.base_url is not None:
        p.base_url = payload.base_url
    if payload.api_key is not None:
        p.api_key = payload.api_key
    if payload.models is not None:
        p.models_json = json.dumps(payload.models)

    await db.commit()
    await db.refresh(p)
    return _to_out(p)


@router.delete("/{provider_id}")
async def delete_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    p = await db.get(ProviderConfig, provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Provider 不存在")
    await db.delete(p)
    await db.commit()
    return {"ok": True}


@router.post("/test")
async def test_provider(payload: ProviderTest, db: AsyncSession = Depends(get_db)):
    if payload.id:
        p = await db.get(ProviderConfig, payload.id)
        if p is None:
            raise HTTPException(status_code=404, detail="Provider 不存在")
    else:
        p = ProviderConfig(
            name=payload.name or "test",
            type=payload.type,
            base_url=payload.base_url,
            api_key=payload.api_key,
            models_json=json.dumps(payload.models),
            is_default=False,
        )
    provider = build_provider(p)
    try:
        models = await provider.list_models()
        return {"ok": True, "models": models}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}