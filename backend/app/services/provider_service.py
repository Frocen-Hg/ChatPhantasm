from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import ModelRoute, ProviderConfig
from ..providers.base import EmbeddingProvider, LLMProvider
from ..providers.ollama import OllamaProvider
from ..providers.openai_compat import OpenAICompatProvider

# 各类型 Provider 的默认嵌入模型（DeepSeek 等无 embeddings 端点，需另配 Provider）
DEFAULT_EMBED_MODELS = {
    "openai_compat": "text-embedding-3-small",
    "ollama": "nomic-embed-text",
}


def build_provider(provider: ProviderConfig) -> LLMProvider:
    """根据 Provider 配置行构建具体 LLM 实例"""
    if provider.type == "ollama":
        return OllamaProvider(
            base_url=provider.base_url,
            default_model=provider.models[0] if provider.models else "",
        )
    return OpenAICompatProvider(
        api_key=provider.api_key or "",
        base_url=provider.base_url,
        default_model=provider.models[0] if provider.models else "deepseek-chat",
    )


def embedding_model_for(provider: ProviderConfig) -> str:
    """嵌入模型：provider.embedding_model > 全局 settings > 类型默认"""
    return (
        provider.embedding_model
        or settings.embedding_model
        or DEFAULT_EMBED_MODELS.get(provider.type, "text-embedding-3-small")
    )


def build_embedding_provider(provider: ProviderConfig) -> EmbeddingProvider:
    """构建嵌入实例（模型独立于聊天模型；同端点可自行实现 chat+embed）"""
    embed_model = embedding_model_for(provider)
    if provider.type == "ollama":
        return OllamaProvider(
            base_url=provider.base_url,
            default_model=provider.models[0] if provider.models else "",
            default_embed_model=embed_model,
        )
    return OpenAICompatProvider(
        api_key=provider.api_key or "",
        base_url=provider.base_url,
        default_model=provider.models[0] if provider.models else "deepseek-chat",
        default_embed_model=embed_model,
    )


# ---- 功能位路由（capability → provider/model）----


async def get_route(db: AsyncSession, capability: str) -> ModelRoute | None:
    return await db.get(ModelRoute, capability)


async def upsert_route(
    db: AsyncSession,
    capability: str,
    provider: ProviderConfig,
    model: str = "",
    params: dict | None = None,
    enabled: bool = True,
) -> ModelRoute:
    route = await db.get(ModelRoute, capability)
    if route is None:
        route = ModelRoute(capability=capability)
        db.add(route)
    route.provider_id = provider.id
    route.model = model or ""
    route.params_json = _dump(params or {})
    route.enabled = enabled
    await db.flush()
    return route


async def delete_route(db: AsyncSession, capability: str) -> None:
    route = await db.get(ModelRoute, capability)
    if route is not None:
        await db.delete(route)
        await db.flush()


async def _default_embedding_provider(db: AsyncSession) -> ProviderConfig | None:
    """嵌入 Provider 兜底：is_embedding_default > 聊天默认"""
    result = await db.execute(
        select(ProviderConfig).where(ProviderConfig.is_embedding_default.is_(True)).limit(1)
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        result = await db.execute(
            select(ProviderConfig).where(ProviderConfig.is_default.is_(True)).limit(1)
        )
        provider = result.scalar_one_or_none()
    return provider


async def resolve_embedding_provider(db: AsyncSession) -> tuple[EmbeddingProvider, str, int]:
    """选取嵌入 Provider：优先 model_routes['embedding']，否则 is_embedding_default / 聊天默认。

    返回 (实例, 模型名, provider_id)。一个向量 collection 必须锁定同一模型，
    因此模型名一并返回，供上层校验/记录。
    """
    route = await get_route(db, "embedding")
    provider: ProviderConfig | None = None
    model = ""
    if route is not None and route.enabled:
        provider = await db.get(ProviderConfig, route.provider_id)
        model = route.model
    if provider is None:
        provider = await _default_embedding_provider(db)
    if provider is None:
        raise ValueError("没有可用于嵌入的 Provider，请先在「设置」中添加并指定")
    return build_embedding_provider(provider), model or embedding_model_for(provider), provider.id


def _dump(value: dict) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
