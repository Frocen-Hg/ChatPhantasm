from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from .base import EmbeddingProvider, LLMProvider


class OpenAICompatProvider(LLMProvider, EmbeddingProvider):
    """OpenAI 兼容端点（DeepSeek / OpenAI / OpenRouter / Moonshot 等）"""

    def __init__(self, api_key: str = "", base_url: str = "", default_model: str = "deepseek-chat"):
        self.default_model = default_model
        self.client = AsyncOpenAI(
            api_key=api_key or "sk-placeholder",
            base_url=base_url or None,
        )

    async def list_models(self) -> list[str]:
        try:
            resp = await self.client.models.list()
            return [m.id for m in resp.data]
        except Exception:
            return [self.default_model]

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self.client.embeddings.create(model="text-embedding-3-small", input=texts)
        return [d.embedding for d in resp.data]