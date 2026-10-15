"""ChromaDB 服务模式实现（chromadb-client AsyncHttpClient，cosine 空间）。

注意：`chromadb.AsyncHttpClient` 是 async 工厂函数，客户端需在异步上下文中惰性创建。
"""

import logging
from urllib.parse import urlparse

from .base import VectorHit, VectorStore

logger = logging.getLogger(__name__)


def _parse_url(url: str) -> tuple[str, int, bool]:
    p = urlparse(url)
    ssl = p.scheme == "https"
    return (p.hostname or "localhost", p.port or (443 if ssl else 8000), ssl)


class ChromaVectorStore(VectorStore):
    def __init__(self, url: str, token: str = "") -> None:
        self._url = url
        self._token = token
        self._client = None
        self._collections: dict[str, object] = {}

    async def _get_client(self):
        if self._client is None:
            from chromadb import AsyncHttpClient  # 延迟导入：未启用向量层时无需该依赖

            host, port, ssl = _parse_url(self._url)
            headers = {"Authorization": f"Bearer {self._token}"} if self._token else None
            self._client = await AsyncHttpClient(host=host, port=port, ssl=ssl, headers=headers)
        return self._client

    async def _collection(self, name: str):
        if name in self._collections:
            return self._collections[name]
        client = await self._get_client()
        try:
            col = await client.get_or_create_collection(
                name=name, configuration={"hnsw": {"space": "cosine"}}
            )
        except TypeError:  # 旧版客户端只认 metadata 形式
            col = await client.get_or_create_collection(
                name=name, metadata={"hnsw:space": "cosine"}
            )
        self._collections[name] = col
        return col

    async def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        col = await self._collection(collection)
        await col.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    async def query(
        self,
        collection: str,
        embedding: list[float],
        top_k: int,
        where: dict | None = None,
    ) -> list[VectorHit]:
        col = await self._collection(collection)
        res = await col.query(
            query_embeddings=[embedding],
            n_results=max(1, top_k),
            where=where,
            include=["metadatas", "distances"],
        )
        ids = (res.get("ids") or [[]])[0]
        distances = (res.get("distances") or [[]])[0]
        metadatas = (res.get("metadatas") or [[]])[0]
        hits: list[VectorHit] = []
        for i, vid in enumerate(ids):
            distance = distances[i] if i < len(distances) else 1.0
            meta = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
            hits.append(VectorHit(id=str(vid), score=1.0 - float(distance), metadata=dict(meta)))
        return hits

    async def delete(self, collection: str, ids: list[str]) -> None:
        col = await self._collection(collection)
        await col.delete(ids=ids)

    async def drop(self, collection: str) -> None:
        self._collections.pop(collection, None)
        try:
            client = await self._get_client()
            await client.delete_collection(collection)
        except Exception:  # noqa: BLE001 集合不存在/服务不可达等情况静默
            logger.debug("drop collection 失败/不存在：%s", collection)

    async def count(self, collection: str) -> int:
        col = await self._collection(collection)
        return int(await col.count())

    async def heartbeat(self) -> bool:
        try:
            client = await self._get_client()
            await client.heartbeat()
            return True
        except Exception:  # noqa: BLE001 服务不可达
            return False
