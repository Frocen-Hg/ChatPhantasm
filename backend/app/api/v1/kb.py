from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...db.models import Character, KbDocument, KbLore
from ...db.session import get_db
from ...schemas.kb import DocumentCreate, KbSearchRequest, LoreCreate, LoreUpdate
from ...services import kb_service, memory_service

router = APIRouter(prefix="/kb", tags=["knowledge"])

ALLOWED_SUFFIXES = (".txt", ".md")


async def _require_character(db: AsyncSession, character_id: int) -> Character:
    character = await db.get(Character, character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return character


async def _require_document(db: AsyncSession, document_id: int) -> KbDocument:
    document = await db.get(KbDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return document


@router.post("/characters/{character_id}/documents")
async def create_document(
    character_id: int,
    payload: DocumentCreate,
    db: AsyncSession = Depends(get_db),
):
    """粘贴文本导入：同步分块落库，索引由 worker 异步完成"""
    character = await _require_character(db, character_id)
    try:
        document = await kb_service.create_document(
            db,
            character,
            title=payload.title,
            text=payload.text,
            scope=payload.scope,
            visibility=payload.visibility,
            chunk_size=payload.chunk_size,
            chunk_overlap=payload.chunk_overlap,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await kb_service.document_dict(db, document)


@router.post("/characters/{character_id}/documents/upload")
async def upload_document(
    character_id: int,
    file: UploadFile,
    scope: str = "world",
    visibility: str = "public",
    db: AsyncSession = Depends(get_db),
):
    """上传 .txt/.md 文件导入（UTF-8）"""
    character = await _require_character(db, character_id)
    name = file.filename or "upload.txt"
    if not name.lower().endswith(ALLOWED_SUFFIXES):
        raise HTTPException(status_code=400, detail="仅支持 .txt / .md 文件")
    raw = await file.read()
    if len(raw) > settings.kb_upload_max_bytes:
        raise HTTPException(
            status_code=400, detail=f"文件超过 {settings.kb_upload_max_bytes} 字节上限"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="文件需为 UTF-8 编码")
    try:
        document = await kb_service.create_document(
            db,
            character,
            title=name,
            text=text,
            source_type="file",
            source_uri=name,
            scope=scope,
            visibility=visibility,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await kb_service.document_dict(db, document)


@router.get("/characters/{character_id}/documents")
async def list_documents(character_id: int, db: AsyncSession = Depends(get_db)):
    await _require_character(db, character_id)
    return await kb_service.list_documents(db, character_id)


@router.get("/documents/{document_id}/chunks")
async def list_chunks(document_id: int, db: AsyncSession = Depends(get_db)):
    await _require_document(db, document_id)
    chunks = await kb_service.list_chunks(db, document_id)
    return [
        {
            "id": c.id,
            "seq": c.seq,
            "content": c.content,
            "tokens": c.tokens,
            "indexed": c.embedding_id is not None,
        }
        for c in chunks
    ]


@router.delete("/documents/{document_id}")
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)):
    document = await _require_document(db, document_id)
    await kb_service.delete_document(db, document)
    return {"ok": True}


@router.post("/documents/{document_id}/reindex")
async def reindex_document(document_id: int, db: AsyncSession = Depends(get_db)):
    """重建该文档的向量索引（换嵌入模型 / 补历史数据 / 失败重试）"""
    document = await _require_document(db, document_id)
    document = await kb_service.reindex_document(db, document)
    return await kb_service.document_dict(db, document)


# ---- lore 条目 ----


@router.get("/characters/{character_id}/lore")
async def list_lore(character_id: int, db: AsyncSession = Depends(get_db)):
    await _require_character(db, character_id)
    lores = await kb_service.list_lore(db, character_id)
    return [kb_service.lore_dict(lore) for lore in lores]


@router.post("/characters/{character_id}/lore")
async def create_lore(
    character_id: int,
    payload: LoreCreate,
    db: AsyncSession = Depends(get_db),
):
    await _require_character(db, character_id)
    lore = await kb_service.create_lore(db, character_id, payload)
    return kb_service.lore_dict(lore)


@router.patch("/lore/{lore_id}")
async def update_lore(
    lore_id: int,
    payload: LoreUpdate,
    db: AsyncSession = Depends(get_db),
):
    lore = await db.get(KbLore, lore_id)
    if lore is None:
        raise HTTPException(status_code=404, detail="lore 不存在")
    lore = await kb_service.update_lore(db, lore, payload)
    return kb_service.lore_dict(lore)


@router.delete("/lore/{lore_id}")
async def delete_lore(lore_id: int, db: AsyncSession = Depends(get_db)):
    lore = await db.get(KbLore, lore_id)
    if lore is None:
        raise HTTPException(status_code=404, detail="lore 不存在")
    await kb_service.delete_lore(db, lore)
    return {"ok": True}


@router.post("/search")
async def search_knowledge(payload: KbSearchRequest, db: AsyncSession = Depends(get_db)):
    """检索预览：lore 命中（constant/关键词）+ 向量召回 + 组装区块（不调 LLM、不落库）"""
    character = await _require_character(db, payload.character_id)
    recent_texts = None
    if payload.conversation_id:
        history = await memory_service.load_history(
            db, payload.conversation_id, limit=settings.kb_scan_depth
        )
        recent_texts = [m["content"] for m in history] + [payload.query]
    return await kb_service.search_knowledge(
        db, character, payload.query, recent_texts, payload.budget_tokens
    )
