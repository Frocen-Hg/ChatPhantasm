from fastapi import APIRouter

from . import characters, chat, conversations, heartbeat, kb, memory, providers, qq, ws

api_router = APIRouter()
api_router.include_router(chat.router)
api_router.include_router(characters.router)
api_router.include_router(conversations.router)
api_router.include_router(providers.router)
api_router.include_router(memory.router)
api_router.include_router(kb.router)
api_router.include_router(heartbeat.router)
api_router.include_router(qq.router)
api_router.include_router(ws.router)


@api_router.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}