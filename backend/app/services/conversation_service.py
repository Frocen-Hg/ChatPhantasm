from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Conversation, Message


async def list_conversations(db: AsyncSession, character_id: int, limit: int = 50) -> list[dict]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.character_id == character_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
    )
    items = []
    for conv in result.scalars().all():
        last = await _last_message(db, conv.id)
        items.append(
            {
                "id": conv.id,
                "character_id": conv.character_id,
                "title": conv.title,
                "message_count": await _message_count(db, conv.id),
                "last_message": last["content"][:100] if last else "",
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
            }
        )
    return items


async def list_messages(db: AsyncSession, conversation_id: int, limit: int = 200) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    rows = list(reversed(result.scalars().all()))
    return [
        {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at}
        for m in rows
    ]


async def _message_count(db: AsyncSession, conversation_id: int) -> int:
    count = await db.execute(
        select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
    )
    return count.scalar_one()


async def _last_message(db: AsyncSession, conversation_id: int) -> dict | None:
    row = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return {"role": row.role, "content": row.content}