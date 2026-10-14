import json
from collections.abc import AsyncIterator

import httpx

from .base import EmbeddingProvider, LLMProvider


class OllamaProvider(LLMProvider, EmbeddingProvider):
    """本地 Ollama 模型接入"""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "",
        default_embed_model: str = "nomic-embed-text",
    ):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.default_embed_model = default_embed_model

    async def list_models(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []

    async def chat(
        self,
        messages: list[dict],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5, read=120, write=120, pool=5)
        ) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    delta = data.get("message", {}).get("content")
                    if delta:
                        yield delta

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/api/embed",
                json={"model": model or self.default_embed_model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
            if "embeddings" in data:
                return data["embeddings"]
            return [data["embedding"]]