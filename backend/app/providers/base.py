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
    """向量化接口抽象（RAG 记忆/知识库复用）"""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...