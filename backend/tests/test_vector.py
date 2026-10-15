"""向量层专项测试：混合检索、语义召回、降级、索引/删除/清理。

用法（仓库根目录）：
    python backend/tests/test_vector.py

退出码：0 = 全部通过；1 = 存在失败。
使用独立临时 SQLite + 内存版 FakeStore/FakeEmbedder，不依赖 Chroma 服务与真实 LLM。
"""
import asyncio
import json
import math
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_tmp = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(Path(_tmp.name) / 'vector.db').as_posix()}"

try:
    from sqlalchemy import select  # noqa: E402

    from app.db.models import Character, Memory  # noqa: E402
    from app.db.session import SessionLocal, engine, init_db  # noqa: E402
    from app.rag.base import VectorHit, VectorStore  # noqa: E402
    from app.seed import seed_defaults  # noqa: E402
    from app.services import memory_service, vector_service  # noqa: E402
except Exception:
    traceback.print_exc()
    sys.exit(1)

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"[PASS] {name}")
    else:
        FAILED += 1
        print(f"[FAIL] {name}  {detail}")


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


class FakeStore(VectorStore):
    """内存向量库：cosine 相似度，语义同 FakeEmbedder"""

    def __init__(self) -> None:
        self.data: dict[str, dict[str, tuple[list[float], dict]]] = {}

    async def upsert(self, collection, ids, embeddings, documents, metadatas) -> None:
        col = self.data.setdefault(collection, {})
        for i, vid in enumerate(ids):
            col[vid] = (embeddings[i], metadatas[i])

    async def query(self, collection, embedding, top_k, where=None) -> list[VectorHit]:
        hits = [
            VectorHit(id=vid, score=_cos(embedding, vec), metadata=meta)
            for vid, (vec, meta) in self.data.get(collection, {}).items()
        ]
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    async def delete(self, collection, ids) -> None:
        col = self.data.get(collection, {})
        for vid in ids:
            col.pop(vid, None)

    async def drop(self, collection) -> None:
        self.data.pop(collection, None)

    async def count(self, collection) -> int:
        return len(self.data.get(collection, {}))

    async def heartbeat(self) -> bool:
        return True


def _vector_for(text: str) -> list[float]:
    """极简语义：潜水/水肺同向，股市正交"""
    if any(k in text for k in ("潜水", "水肺", "scuba")):
        return [1.0, 0.0]
    if "股市" in text:
        return [0.0, 1.0]
    return [0.5, 0.5]


async def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [_vector_for(t) for t in texts]


async def _new_character(db, name: str) -> Character:
    char = Character(
        name=name,
        card_json=json.dumps({"name": name}, ensure_ascii=False),
        ext_json="{}",
    )
    db.add(char)
    await db.commit()
    await db.refresh(char)
    return char


async def test_index_and_search(db) -> None:
    char = await _new_character(db, "向量测试")
    m1 = Memory(character_id=char.id, layer="L3", kind="fact", content="喜欢潜水", importance=8.0)
    m2 = Memory(character_id=char.id, layer="L3", kind="fact", content="股市大跌", importance=8.0)
    db.add_all([m1, m2])
    await db.commit()

    indexed = await vector_service.index_memories(db, char.id, [m1, m2])
    check("索引写入向量", indexed == 2, f"indexed={indexed}")
    check("回填 embedding_id", m1.embedding_id == str(m1.id) and m2.embedding_id == str(m2.id), f"{m1.embedding_id}/{m2.embedding_id}")

    sims = await vector_service.search_memory_vectors(db, char.id, "水肺")
    check(
        "向量检索返回相似度",
        sims.get(m1.id, 0) > 0.99 and sims.get(m2.id, 1) < 0.01,
        f"sims={sims}",
    )


async def test_hybrid_semantic_recall(db) -> None:
    char = (await db.execute(select(Character).where(Character.name == "向量测试"))).scalar_one()
    # query「水肺」与「喜欢潜水」无关键词交集，仅靠向量召回
    picked = await memory_service.retrieve(db, char.id, "水肺", 5, 30.0, touch=False)
    contents = [m.content for m in picked]
    check("语义召回：无关键词交集也能命中", "喜欢潜水" in contents, f"contents={contents}")
    check("向量不相似者被过滤", "股市大跌" not in contents, f"contents={contents}")

    results = await memory_service.search_memories(db, char.id, "水肺", 5)
    top = next((r for r in results if r["content"] == "喜欢潜水"), None)
    check(
        "预览含向量分与混合分",
        top is not None and top["vector"] is not None and top["keyword"] == 0.0 and top["score"] > 0,
        f"top={top}",
    )


async def test_keyword_only_without_vector(db) -> None:
    char = (await db.execute(select(Character).where(Character.name == "向量测试"))).scalar_one()
    # 关键词能命中的记忆仍可用
    picked = await memory_service.retrieve(db, char.id, "潜水", 5, 30.0, touch=False)
    check("关键词命中仍可用", any(m.content == "喜欢潜水" for m in picked), f"{[m.content for m in picked]}")


async def test_graceful_degradation(db) -> None:
    char = (await db.execute(select(Character).where(Character.name == "向量测试"))).scalar_one()
    vector_service.set_store(None)  # 关闭向量库（且关闭 enable 后 get_store 也不建）
    vector_service.set_embedder(None)

    import app.config as config_module

    original = config_module.settings.chroma_enabled
    config_module.settings.chroma_enabled = False
    try:
        picked = await memory_service.retrieve(db, char.id, "潜水", 5, 30.0, touch=False)
        check("向量不可用时降级为纯 SQL", any(m.content == "喜欢潜水" for m in picked), f"{[m.content for m in picked]}")
        results = await memory_service.search_memories(db, char.id, "潜水", 5)
        check("降级预览 vector 为 None", all(r["vector"] is None for r in results), f"{results}")
    finally:
        config_module.settings.chroma_enabled = original
        vector_service.set_store(FakeStore())
        vector_service.set_embedder(_fake_embed)


async def test_delete_and_drop(db) -> None:
    char = await _new_character(db, "向量清理")
    m = Memory(character_id=char.id, layer="L3", kind="fact", content="喜欢潜水", importance=5.0)
    db.add(m)
    await db.commit()
    await vector_service.index_memories(db, char.id, [m])

    store = vector_service.get_store()
    check("索引后集合非空", await store.count(vector_service.memory_collection(char.id)) == 1)

    await memory_service.delete_memory(db, m)
    check("删除记忆同步删向量", await store.count(vector_service.memory_collection(char.id)) == 0)

    m2 = Memory(character_id=char.id, layer="L3", kind="fact", content="喜欢潜水", importance=5.0)
    db.add(m2)
    await db.commit()
    await vector_service.index_memories(db, char.id, [m2])
    await vector_service.drop_character(char.id)
    check("删除角色清理向量集合", vector_service.memory_collection(char.id) not in store.data)


async def test_sync_and_reindex(db) -> None:
    from app.schemas.memory import MemoryCreate, MemoryUpdate

    char = await _new_character(db, "索引同步")
    store = vector_service.get_store()
    col = vector_service.memory_collection(char.id)

    memory = await memory_service.create_memory(
        db, char.id, MemoryCreate(content="喜欢潜水", kind="fact", layer="L3", importance=7)
    )
    check("新建记忆自动索引", await store.count(col) == 1, f"count={await store.count(col)}")

    await memory_service.update_memory(db, memory, MemoryUpdate(visibility="private"))
    check("改私有后移出索引", await store.count(col) == 0, f"count={await store.count(col)}")

    await memory_service.update_memory(
        db, memory, MemoryUpdate(visibility="public", content="喜欢水肺潜水")
    )
    check("改回公开后重建索引", await store.count(col) == 1, f"count={await store.count(col)}")

    await vector_service.drop_character(char.id)
    indexed = await memory_service.reindex_memories(db, char.id)
    check(
        "重建索引恢复集合",
        indexed == 1 and await store.count(col) == 1,
        f"indexed={indexed}",
    )


async def run() -> None:
    await init_db()
    await seed_defaults()
    vector_service.set_store(FakeStore())
    vector_service.set_embedder(_fake_embed)
    try:
        async with SessionLocal() as db:
            await test_index_and_search(db)
            await test_hybrid_semantic_recall(db)
            await test_keyword_only_without_vector(db)
            await test_graceful_degradation(db)
            await test_delete_and_drop(db)
            await test_sync_and_reindex(db)
    finally:
        vector_service.reset()

    await engine.dispose()
    try:
        _tmp.cleanup()
    except Exception:
        pass
    print(f"\n结果：{PASSED} 通过 / {FAILED} 失败")
    sys.exit(1 if FAILED else 0)


def main() -> None:
    try:
        asyncio.run(run())
    except Exception:
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
