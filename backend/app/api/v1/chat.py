from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import Character
from ...db.session import get_db
from ...schemas.chat import ChatRequest
from ...services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    character = await db.get(Character, req.character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="角色不存在")

    conversation = await chat_service.get_or_create_conversation(db, req.character_id, req.conversation_id)
    provider, model_cfg = await chat_service.resolve_provider(
        db, character, provider_id=req.provider_id, model=req.model
    )

    async def gen():
        try:
            async for token in chat_service.stream_reply(db, conversation, character, provider, model_cfg, req.content):
                yield token
        except Exception as e:  # noqa: BLE001  流式响应中途异常：输出错误而非断连
            yield f"\n\n（错误）{e}"

    return StreamingResponse(
        gen(),
        media_type="text/plain; charset=utf-8",
        headers={"X-Conversation-Id": str(conversation.id)},
    )