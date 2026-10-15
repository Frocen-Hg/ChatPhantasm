"""知识库编排：导入/分块、异步索引（outbox worker）、文档管理。

与记忆一致：SQL 为唯一事实源（分块持久化），向量库只是索引；向量层不可用时静默降级
（分块仍入库，lore 的常驻/关键词通道照常工作，仅语义召回失效）。
"""

import asyncio
import contextlib
import logging
import re
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import Character, KbChunk, KbDocument, KbJob
from ..db.session import SessionLocal
from . import vector_service
from .memory_service import estimate_tokens

logger = logging.getLogger(__name__)

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def chunk_text(text: str, chunk_size: int, overlap: int, max_chunks: int) -> list[str]:
    """Markdown 感知分块：按标题分段（标题链前缀进块）+ 段落聚合到 chunk_size。

    超长段落硬切并保留 overlap；总量截断到 max_chunks。
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    chunk_size = max(100, int(chunk_size))
    overlap = max(0, min(int(overlap), chunk_size // 2))

    sections: list[tuple[str, str]] = []
    heading_stack: list[str] = []
    prefix = ""
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        body = "\n".join(buf).strip()
        if body:
            sections.append((prefix, body))
        buf = []

    for line in text.split("\n"):
        match = _HEADING.match(line.strip())
        if match:
            flush()
            level = len(match.group(1))
            heading_stack[:] = heading_stack[: level - 1]
            heading_stack.append(line.strip())
            prefix = "\n".join(heading_stack) + "\n"
        else:
            buf.append(line)
    flush()

    chunks: list[str] = []
    for sec_prefix, body in sections:
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        cur = ""
        for para in paras:
            if len(para) > chunk_size:
                if cur:
                    chunks.append(sec_prefix + cur)
                    cur = ""
                start = 0
                while start < len(para):
                    chunks.append(sec_prefix + para[start : start + chunk_size])
                    start += chunk_size - overlap
                continue
            if cur and len(cur) + 1 + len(para) > chunk_size:
                chunks.append(sec_prefix + cur)
                tail = cur[-overlap:] if overlap else ""
                cur = f"{tail}\n{para}".strip() if tail else para
            else:
                cur = f"{cur}\n{para}" if cur else para
        if cur:
            chunks.append(sec_prefix + cur)

    return [c for c in chunks if c.strip()][:max_chunks]


async def create_document(
    db: AsyncSession,
    character: Character,
    *,
    title: str,
    text: str,
    source_type: str = "text",
    source_uri: str = "",
    scope: str = "world",
    visibility: str = "public",
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> KbDocument:
    """导入文档：同步解析+分块落库，索引交由 kb worker 异步完成"""
    kb_cfg = character.ext.get("knowledge") or {}
    size = int(chunk_size or kb_cfg.get("chunk_size", settings.kb_chunk_size))
    overlap = int(
        chunk_overlap
        if chunk_overlap is not None
        else kb_cfg.get("chunk_overlap", settings.kb_chunk_overlap)
    )
    max_chunks = int(kb_cfg.get("max_chunks", settings.kb_max_chunks_per_doc))

    pieces = chunk_text(text, size, overlap, max_chunks)
    if not pieces:
        raise ValueError("内容为空，无法分块")

    doc = KbDocument(
        character_id=character.id,
        title=(title or "未命名文档")[:128],
        source_type=source_type,
        source_uri=(source_uri or "")[:255],
        scope=scope,
        visibility=visibility,
        chunk_size=size,
        chunk_overlap=overlap,
        status="pending",
        chunk_count=len(pieces),
    )
    db.add(doc)
    await db.flush()
    for i, piece in enumerate(pieces):
        db.add(
            KbChunk(
                document_id=doc.id,
                character_id=character.id,
                seq=i,
                content=piece,
                tokens=estimate_tokens(piece),
            )
        )
    db.add(KbJob(document_id=doc.id, character_id=character.id, status="pending"))
    await db.commit()
    await db.refresh(doc)
    return doc


async def _indexed_count(db: AsyncSession, document_id: int) -> int:
    result = await db.execute(
        select(func.count(KbChunk.id)).where(
            KbChunk.document_id == document_id, KbChunk.embedding_id.is_not(None)
        )
    )
    return result.scalar_one()


async def document_dict(db: AsyncSession, document: KbDocument) -> dict:
    return {
        "id": document.id,
        "character_id": document.character_id,
        "title": document.title,
        "source_type": document.source_type,
        "source_uri": document.source_uri,
        "scope": document.scope,
        "visibility": document.visibility,
        "chunk_size": document.chunk_size,
        "chunk_overlap": document.chunk_overlap,
        "status": document.status,
        "error": document.error,
        "chunk_count": document.chunk_count,
        "indexed_count": await _indexed_count(db, document.id),
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


async def list_documents(db: AsyncSession, character_id: int) -> list[dict]:
    result = await db.execute(
        select(KbDocument)
        .where(KbDocument.character_id == character_id)
        .order_by(KbDocument.id.desc())
    )
    return [await document_dict(db, doc) for doc in result.scalars().all()]


async def list_chunks(db: AsyncSession, document_id: int) -> list[KbChunk]:
    result = await db.execute(
        select(KbChunk).where(KbChunk.document_id == document_id).order_by(KbChunk.seq)
    )
    return list(result.scalars().all())


async def delete_document(db: AsyncSession, document: KbDocument) -> None:
    chunks = await list_chunks(db, document.id)
    chunk_ids = [c.id for c in chunks]
    character_id = document.character_id
    await db.execute(delete(KbChunk).where(KbChunk.document_id == document.id))
    await db.execute(delete(KbJob).where(KbJob.document_id == document.id))
    await db.delete(document)
    await db.commit()
    await vector_service.delete_document_vectors(character_id, chunk_ids)


async def reindex_document(db: AsyncSession, document: KbDocument) -> KbDocument:
    """清空索引并重新入队（换嵌入模型 / 补历史数据 / 失败重试）"""
    chunks = await list_chunks(db, document.id)
    chunk_ids = [c.id for c in chunks]
    for chunk in chunks:
        chunk.embedding_id = None
    document.status = "pending"
    document.error = ""
    db.add(KbJob(document_id=document.id, character_id=document.character_id, status="pending"))
    await db.commit()
    await db.refresh(document)
    await vector_service.delete_document_vectors(document.character_id, chunk_ids)
    return document


async def index_document(db: AsyncSession, document: KbDocument) -> int:
    """worker 核心：嵌入分块并写入向量库；失败抛异常交由任务层重试"""
    chunks = await list_chunks(db, document.id)
    if not chunks:
        document.status = "indexed"
        document.error = ""
        await db.commit()
        return 0
    indexed = await vector_service.index_chunks(
        db, document.character_id, chunks, document=document
    )
    if indexed == 0:
        raise RuntimeError("向量库不可用或嵌入失败")
    document.status = "indexed"
    document.error = ""
    await db.commit()
    return indexed


# ---- outbox worker（与记忆 worker 同模式，独立轮询）----


async def reset_running_jobs() -> int:
    async with SessionLocal() as db:
        result = await db.execute(select(KbJob).where(KbJob.status == "running"))
        jobs = list(result.scalars().all())
        for job in jobs:
            job.status = "pending"
        if jobs:
            await db.commit()
        return len(jobs)


async def _claim_job(db: AsyncSession) -> KbJob | None:
    result = await db.execute(
        select(KbJob)
        .where(KbJob.status == "pending", KbJob.run_after <= datetime.now())
        .order_by(KbJob.id)
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if job is not None:
        job.status = "running"
        await db.commit()
        await db.refresh(job)
    return job


async def _process_job(db: AsyncSession, job: KbJob) -> None:
    document = await db.get(KbDocument, job.document_id)
    if document is None:
        return  # 文档已删，任务作废
    await index_document(db, document)


async def run_worker_once(processor=None) -> bool:
    async with SessionLocal() as db:
        job = await _claim_job(db)
        if job is None:
            return False
        handle = processor or _process_job
        try:
            await handle(db, job)
            job.status = "done"
        except Exception as e:  # noqa: BLE001 单任务失败不拖垮 worker
            job.attempts = (job.attempts or 0) + 1
            job.last_error = str(e)[:500]
            if job.attempts >= settings.kb_job_max_attempts:
                job.status = "failed"
                document = await db.get(KbDocument, job.document_id)
                if document is not None and document.status != "indexed":
                    document.status = "failed"
                    document.error = job.last_error
            else:
                job.status = "pending"
                job.run_after = datetime.now() + timedelta(seconds=5 * job.attempts)
            logger.warning("知识库任务 #%s 处理失败（第 %s 次）：%s", job.id, job.attempts, e)
        await db.commit()
        return True


async def worker_loop() -> None:
    while True:
        try:
            processed = await run_worker_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("知识库 worker 异常：%s", e)
            processed = False
        if not processed:
            await asyncio.sleep(settings.kb_worker_interval)


async def start_worker() -> asyncio.Task | None:
    if not settings.kb_enabled:
        return None
    await reset_running_jobs()
    return asyncio.create_task(worker_loop())


async def stop_worker(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task
