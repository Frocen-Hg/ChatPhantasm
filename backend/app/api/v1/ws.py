import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...config import settings
from ...services import ws_service

router = APIRouter(tags=["ws"])


def _is_ping(raw: str) -> bool:
    if raw.strip() == "ping":
        return True
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False
    return isinstance(data, dict) and data.get("type") == "ping"


@router.websocket("/ws")
async def ws_endpoint(
    websocket: WebSocket,
    character_id: int | None = None,
    conversation_id: int | None = None,
    token: str | None = None,
):
    """心跳事件订阅：?character_id=&conversation_id=&token= 均为可选筛选/鉴权

    不加筛选则接收全部角色的事件；保活 = 客户端 ping ↔ 服务端 pong +
    空闲 `ws_ping_interval` 秒后服务端主动 ping。
    """
    if settings.ws_token and token != settings.ws_token:
        await websocket.close(code=4401)
        return
    manager = ws_service.get_manager()
    conn = await manager.connect(websocket, character_id, conversation_id)
    try:
        while True:
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(), timeout=settings.ws_ping_interval
                )
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
                continue
            if _is_ping(raw):
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(conn)
