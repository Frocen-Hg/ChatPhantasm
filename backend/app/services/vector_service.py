"""向量层编排：embedding 解析、记忆索引与检索、可用性降级、测试注入点。

设计原则：向量层是**可选增强**——Chroma 不可达或嵌入未配置时，全部静默降级为纯 SQL 检索。
"""

import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import Memory
from ..rag.base import VectorStore
from ..rag.chroma_store import ChromaVectorStore
from .provider_service import resolve_embedding_provider

logger = logging.getLogger(__name__)

_store: VectorStore | None = None
_embedder = None  # 测试注入：async (texts: list[str]) -> list[list[float]]
_probe: tuple[float, bool] | None = None
_PROBE_TTL = 30.0


def memory_collection(character_id: int) -> str:
    return f"char{character_id}_mem"


def kb_collection(character_id: int) -> str:
    return f"char{character_id}_kb"


def get_store() -> VectorStore | None:
    global _store
    if not settings.chroma_enabled:
        return None
    if _store is None:
        _store = ChromaVectorStore(settings.chroma_url, settings.chroma_auth_token)
    return _store


def set_store(store: VectorStore | None) -> None:
    """测试注入：替换/禁用向量库实现"""
    global _store, _probe
    _store = store
    _probe = None


def set_embedder(embedder) -> None:
    """测试注入：async (texts) -> vectors"""
    global _embedder
    _embedder = embedder


def reset() -> None:
    global _store, _embedder, _probe
    _store = None
    _embedder = None
    _probe = None


async def store_available() -> bool:
    """可用性探测（30s 缓存），失败即降级"""
    global _probe
    store = get_store()
    if store is None:
        return False
    now = time.monotonic()
    if _probe is not None and now - _probe[0] < _PROBE_TTL:
        return _probe[1]
    ok = await store.heartbeat()
    _probe = (now, ok)
    if not ok:
        logger.warning("向量库不可用（%s），降级为纯 SQL 检索", settings.chroma_url)
    return ok


async def embed_texts(db: AsyncSession, texts: list[str]) -> list[list[float]] | None:
    """解析嵌入 Provider 并向量化；失败返回 None（降级）"""
    if _embedder is not None:
        return await _embedder(texts)
    try:
        provider, model, _provider_id = await resolve_embedding_provider(db)
        return await provider.embed(texts, model=model)
    except Exception as e:  # noqa: BLE001
        logger.warning("嵌入失败，降级为纯 SQL 检索：%s", e)
        return None


async def index_memories(db: AsyncSession, character_id: int, memories: list[Memory]) -> int:
    """把记忆写入向量集合并回填 embedding_id；不可用时返回 0"""
    if not memories or not await store_available():
        return 0
    store = get_store()
    if store is None:
        return 0
    vectors = await embed_texts(db, [m.content for m in memories])
    if vectors is None:
        return 0
    await store.upsert(
        memory_collection(character_id),
        [str(m.id) for m in memories],
        vectors,
        [m.content for m in memories],
        [
            {
                "character_id": character_id,
                "layer": m.layer,
                "kind": m.kind,
                "importance": float(m.importance or 0.0),
            }
            for m in memories
        ],
    )
    for m in memories:
        m.embedding_id = str(m.id)
    await db.commit()
    return len(memories)


async def search_memory_vectors(
    db: AsyncSession, character_id: int, query: str, top_k: int | None = None
) -> dict[int, float]:
    """返回 {memory_id: 相似度}；不可用时返回空 dict"""
    if not query or not await store_available():
        return {}
    store = get_store()
    if store is None:
        return {}
    vectors = await embed_texts(db, [query])
    if not vectors:
        return {}
    hits = await store.query(
        memory_collection(character_id), vectors[0], top_k or settings.vector_top_k
    )
    out: dict[int, float] = {}
    for hit in hits:
        try:
            out[int(hit.id)] = hit.score
        except ValueError:
            continue
    return out


async def delete_memory_vectors(character_id: int, ids: list[int]) -> None:
    if not ids or not await store_available():
        return
    store = get_store()
    if store is None:
        return
    await store.delete(memory_collection(character_id), [str(i) for i in ids])


async def index_chunks(db: AsyncSession, character_id: int, chunks: list, document=None) -> int:
    """把知识库分块写入向量集合并回填 embedding_id；document 提供 scope/visibility 元数据"""
    if not chunks or not await store_available():
        return 0
    store = get_store()
    if store is None:
        return 0
    vectors = await embed_texts(db, [c.content for c in chunks])
    if vectors is None:
        return 0
    scope = getattr(document, "scope", "world") if document is not None else "world"
    visibility = getattr(document, "visibility", "public") if document is not None else "public"
    await store.upsert(
        kb_collection(character_id),
        [str(c.id) for c in chunks],
        vectors,
        [c.content for c in chunks],
        [
            {
                "character_id": character_id,
                "document_id": c.document_id,
                "seq": c.seq,
                "scope": scope,
                "visibility": visibility,
            }
            for c in chunks
        ],
    )
    for c in chunks:
        c.embedding_id = str(c.id)
    await db.commit()
    return len(chunks)


async def delete_document_vectors(character_id: int, chunk_ids: list[int]) -> None:
    if not chunk_ids or not await store_available():
        return
    store = get_store()
    if store is None:
        return
    await store.delete(kb_collection(character_id), [str(i) for i in chunk_ids])


async def search_kb_vectors(
    db: AsyncSession, character_id: int, query: str, top_k: int | None = None
) -> dict[int, float]:
    """知识库语义召回：返回 {chunk_id: 相似度}"""
    if not query or not await store_available():
        return {}
    store = get_store()
    if store is None:
        return {}
    vectors = await embed_texts(db, [query])
    if not vectors:
        return {}
    hits = await store.query(
        kb_collection(character_id), vectors[0], top_k or settings.kb_top_k
    )
    out: dict[int, float] = {}
    for hit in hits:
        try:
            out[int(hit.id)] = hit.score
        except ValueError:
            continue
    return out


async def drop_character(character_id: int) -> None:
    """删除角色时清理其向量集合（记忆 + 知识库）"""
    if not await store_available():
        return
    store = get_store()
    if store is None:
        return
    for collection in (memory_collection(character_id), kb_collection(character_id)):
        await store.drop(collection)
