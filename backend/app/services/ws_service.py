"""WebSocket 心跳事件推送（P3b）：按角色/会话订阅的连接管理器。

范围决策：P3 仅推送心跳事件（聊天仍走 REST 流式）。无用户体系，仅本机/内网使用；
`settings.ws_token` 非空时做连接级 token 校验（预留位）。广播失败逐连接降级，
不影响心跳本身。
"""

import asyncio
import json
import logging
from dataclasses import dataclass

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass(eq=False)
class Connection:
    websocket: WebSocket
    character_id: int | None = None
    conversation_id: int | None = None


class ConnectionManager:
    """连接注册与心跳事件广播（单进程内存态；多实例部署需换 Redis 之类的总线）"""

    def __init__(self) -> None:
        self._connections: set[Connection] = set()
        self._lock = asyncio.Lock()

    async def connect(
        self, websocket: WebSocket, character_id: int | None = None, conversation_id: int | None = None
    ) -> Connection:
        await websocket.accept()
        conn = Connection(websocket=websocket, character_id=character_id, conversation_id=conversation_id)
        async with self._lock:
            self._connections.add(conn)
        return conn

    async def disconnect(self, conn: Connection) -> None:
        async with self._lock:
            self._connections.discard(conn)

    def _matches(self, conn: Connection, character_id: int, conversation_id: int | None) -> bool:
        if conn.character_id is not None and conn.character_id != character_id:
            return False
        if (
            conn.conversation_id is not None
            and conversation_id is not None
            and conn.conversation_id != conversation_id
        ):
            return False
        return True

    async def broadcast_heartbeat(
        self,
        *,
        character_id: int,
        conversation_id: int | None,
        run_id: int,
        run_type: str,
        message: str | None = None,
        monologue: str | None = None,
    ) -> int:
        """推送事件：{"type":"heartbeat","data":{run_id,type,character_id,conversation_id,message|monologue}}"""
        data: dict = {
            "run_id": run_id,
            "type": run_type,
            "character_id": character_id,
            "conversation_id": conversation_id,
        }
        if message is not None:
            data["message"] = message
        if monologue is not None:
            data["monologue"] = monologue
        text = json.dumps({"type": "heartbeat", "data": data}, ensure_ascii=False)
        async with self._lock:
            targets = [
                conn for conn in self._connections if self._matches(conn, character_id, conversation_id)
            ]
        sent = 0
        for conn in targets:
            try:
                await conn.websocket.send_text(text)
                sent += 1
            except Exception as e:  # noqa: BLE001 连接异常逐出，不影响其他连接
                logger.info("WS 推送失败，移除连接：%s", e)
                await self.disconnect(conn)
        return sent


_manager = ConnectionManager()


def get_manager() -> ConnectionManager:
    return _manager


async def broadcast_heartbeat(**kwargs) -> int:
    return await _manager.broadcast_heartbeat(**kwargs)
