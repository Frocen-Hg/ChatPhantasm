from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import Conversation, Message
from ...db.session import get_db
from ...services import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(character_id: int, db: AsyncSession = Depends(get_db)):
    return await conversation_service.list_conversations(db, character_id)


@router.get("/{conversation_id}/messages")
async def get_messages(conversation_id: int, db: AsyncSession = Depends(get_db)):
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return await conversation_service.list_messages(db, conversation_id)


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int, db: AsyncSession = Depends(get_db)):
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    # 先删消息再删会话（表间无 ON DELETE CASCADE）
    result = await db.execute(select(Message).where(Message.conversation_id == conversation_id))
    for m in result.scalars().all():
        await db.delete(m)
    await db.delete(conversation)
    await db.commit()
    return {"ok": True}