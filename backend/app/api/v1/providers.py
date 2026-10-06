import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import ModelRoute, ProviderConfig
from ...db.session import get_db
from ...schemas.provider import (
    ProviderCreate,
    ProviderTest,
    ProviderUpdate,
    RouteUpsert,
)
from ...services.provider_service import (
    build_embedding_provider,
    build_provider,
    embedding_model_for,
    upsert_route,
)

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
        "is_embedding_default": p.is_embedding_default,
        "embedding_model": p.embedding_model,
        "api_key_masked": _mask_key(p.api_key),
    }


def _route_to_out(r: ModelRoute, p: ProviderConfig | None) -> dict:
    return {
        "capability": r.capability,
        "provider_id": r.provider_id,
        "provider_name": p.name if p else None,
        "model": r.model,
        "params": json.loads(r.params_json or "{}"),
        "enabled": r.enabled,
    }


async def _clear_default(db: AsyncSession) -> None:
    result = await db.execute(select(ProviderConfig).where(ProviderConfig.is_default.is_(True)))
    for p in result.scalars().all():
        p.is_default = False


async def _clear_embedding_default(db: AsyncSession) -> None:
    result = await db.execute(
        select(ProviderConfig).where(ProviderConfig.is_embedding_default.is_(True))
    )
    for p in result.scalars().all():
        p.is_embedding_default = False


# ---- 功能位路由（须声明在 /{provider_id} 之前）----


@router.get("/routes")
async def list_routes(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ModelRoute).order_by(ModelRoute.capability))
    out = []
    for r in result.scalars().all():
        out.append(_route_to_out(r, await db.get(ProviderConfig, r.provider_id)))
    return out


@router.put("/routes/{capability}")
async def set_route(capability: str, payload: RouteUpsert, db: AsyncSession = Depends(get_db)):
    p = await db.get(ProviderConfig, payload.provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Provider 不存在")
    route = await upsert_route(
        db, capability, p, model=payload.model or "", params=payload.params, enabled=payload.enabled
    )
    await db.commit()
    await db.refresh(route)
    return _route_to_out(route, p)


@router.delete("/routes/{capability}")
async def clear_route(capability: str, db: AsyncSession = Depends(get_db)):
    route = await db.get(ModelRoute, capability)
    if route is not None:
        await db.delete(route)
        await db.commit()
    return {"ok": True}


@router.get("")
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProviderConfig).order_by(ProviderConfig.id))
    return [_to_out(p) for p in result.scalars().all()]


@router.post("")
async def create_provider(payload: ProviderCreate, db: AsyncSession = Depends(get_db)):
    if payload.is_default:
        await _clear_default(db)
    if payload.is_embedding_default:
        await _clear_embedding_default(db)
    p = ProviderConfig(
        name=payload.name,
        type=payload.type,
        base_url=payload.base_url,
        api_key=payload.api_key,
        models_json=json.dumps(payload.models),
        is_default=payload.is_default,
        embedding_model=payload.embedding_model,
        is_embedding_default=payload.is_embedding_default,
    )
    db.add(p)
    await db.flush()
    # 布尔开关与功能位路由保持同步（旧 UI 仍可用）
    if payload.is_default:
        await upsert_route(db, "chat", p, model=p.models[0] if p.models else "")
    if payload.is_embedding_default:
        await upsert_route(db, "embedding", p, model=embedding_model_for(p))
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
        p.is_default = False

    if payload.is_embedding_default:
        await _clear_embedding_default(db)
        p.is_embedding_default = True
    elif payload.is_embedding_default is False:
        p.is_embedding_default = False

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
    if payload.embedding_model is not None:
        p.embedding_model = payload.embedding_model

    if payload.is_default:
        await upsert_route(db, "chat", p, model=p.models[0] if p.models else "")
    if payload.is_embedding_default:
        await upsert_route(db, "embedding", p, model=embedding_model_for(p))
    elif payload.embedding_model is not None:
        # 嵌入路由指向本 Provider 时同步模型
        route = await db.get(ModelRoute, "embedding")
        if route is not None and route.provider_id == p.id:
            route.model = embedding_model_for(p)

    await db.commit()
    await db.refresh(p)
    return _to_out(p)


@router.delete("/{provider_id}")
async def delete_provider(provider_id: int, db: AsyncSession = Depends(get_db)):
    p = await db.get(ProviderConfig, provider_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Provider 不存在")
    # 清理引用该 Provider 的功能位路由，避免悬空引用
    refs = await db.execute(select(ModelRoute).where(ModelRoute.provider_id == provider_id))
    for r in refs.scalars().all():
        await db.delete(r)
    await db.delete(p)
    await db.commit()
    return {"ok": True}


@router.post("/test")
async def test_provider(payload: ProviderTest, db: AsyncSession = Depends(get_db)):
    p = await _resolve_test_provider(payload, db)
    if payload.capability == "embedding":
        model = embedding_model_for(p)
        try:
            vectors = await build_embedding_provider(p).embed(["嵌入连通性测试"], model=model)
            return {"ok": True, "model": model, "dim": len(vectors[0]) if vectors else 0}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e), "model": model}
    try:
        models = await build_provider(p).list_models()
        return {"ok": True, "models": models}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


@router.post("/test-embedding")
async def test_embedding(payload: ProviderTest, db: AsyncSession = Depends(get_db)):
    """嵌入连通性测试（保留旧入口）：返回向量维度，便于校验与向量库维度是否一致"""
    payload.capability = "embedding"
    return await test_provider(payload, db)


async def _resolve_test_provider(payload: ProviderTest, db: AsyncSession) -> ProviderConfig:
    if payload.id:
        p = await db.get(ProviderConfig, payload.id)
        if p is None:
            raise HTTPException(status_code=404, detail="Provider 不存在")
        return p
    return ProviderConfig(
        name=payload.name or "test",
        type=payload.type,
        base_url=payload.base_url,
        api_key=payload.api_key,
        models_json=json.dumps(payload.models),
        embedding_model=payload.embedding_model,
        is_default=False,
    )
