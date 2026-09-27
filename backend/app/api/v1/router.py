from fastapi import APIRouter

from . import characters, chat, providers

api_router = APIRouter()
api_router.include_router(chat.router)
api_router.include_router(characters.router)
api_router.include_router(providers.router)


@api_router.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}