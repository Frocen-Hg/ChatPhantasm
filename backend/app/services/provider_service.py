from ..db.models import ProviderConfig
from ..providers.base import EmbeddingProvider, LLMProvider
from ..providers.ollama import OllamaProvider
from ..providers.openai_compat import OpenAICompatProvider


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


def build_embedding_provider(provider: ProviderConfig) -> EmbeddingProvider:
    """同源即可（OpenAI 兼容 / Ollama 均实现 embed），后续 RAG 复用"""
    return build_provider(provider)  # type: ignore[return-value]