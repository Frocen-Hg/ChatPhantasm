"""QQ 群聊插件（NapCat / OneBot 11）。

内置能力：
- OneBot 11 反向 WebSocket 服务端（`/api/v1/qq/ws`）：接收事件、发起 action 并等待 echo。
- 群绑定 / 成员标签 / 回复频率控制，全部复用 ChatPhantasm 的分层记忆与聊天模型。
- 心跳主动消息投递钩子（heartbeat_service 经 plugin_system 调用）。

NapCat 本体仍是外部运行组件（需注入 QQ 客户端），插件负责协议与业务侧。
"""

from fastapi import APIRouter

from app.plugin_system import Plugin

from . import api
from . import service


class QqPlugin(Plugin):
    name = "qq"

    def __init__(self) -> None:
        self.router: APIRouter = api.router
        self.bridge = service.bridge
        self.dispatch_proactive = service.dispatch_proactive

    async def start(self) -> None:
        service.logger.info("QQ 插件已启动（NapCat 反向 WS 入口：/api/v1/qq/ws）")

    async def stop(self) -> None:
        await service.bridge.shutdown()
        service.logger.info("QQ 插件已停止")


plugin = QqPlugin()
