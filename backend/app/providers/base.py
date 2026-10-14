from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    """大模型对话接口抽象（外部 API 与本地 Ollama 均实现）"""

    @abstractmethod
    async def list_models(self) -> list[str]: ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]: ...


class EmbeddingProvider(ABC):
    """向量化接口抽象（RAG 记忆/知识库复用）

    嵌入模型独立于聊天模型，可由 Provider 的 embedding_model 指定；
    模型名作为调用参数显式传入，避免把模型硬编码在实现里。
    """

    @abstractmethod
    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]: ...