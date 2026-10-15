"""向量库抽象：记忆与知识库共用，实现可替换（Chroma 服务模式 / 测试用假实现）"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class VectorHit:
    id: str
    score: float  # 相似度，越大越相似（实现需把距离归一化为此语义）
    metadata: dict = field(default_factory=dict)


class VectorStore(ABC):
    """最小向量库接口（cosine 空间）"""

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None: ...

    @abstractmethod
    async def query(
        self,
        collection: str,
        embedding: list[float],
        top_k: int,
        where: dict | None = None,
    ) -> list[VectorHit]: ...

    @abstractmethod
    async def delete(self, collection: str, ids: list[str]) -> None: ...

    @abstractmethod
    async def drop(self, collection: str) -> None: ...

    @abstractmethod
    async def count(self, collection: str) -> int: ...

    @abstractmethod
    async def heartbeat(self) -> bool:
        """可用性探测；不可用时上层降级为纯 SQL 检索"""
