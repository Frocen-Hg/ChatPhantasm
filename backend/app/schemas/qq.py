"""兼容层：QQ 插件 schema（见 `plugins/qq/schemas.py`），保留原导入路径 `app.schemas.qq`。"""

from ..plugin_system import load_all

load_all()

from plugins.qq.schemas import (  # noqa: E402,F401
    QqBindingCreate,
    QqBindingUpdate,
    QqMemberUpdate,
    QqTestSendRequest,
)

__all__ = [
    "QqBindingCreate",
    "QqBindingUpdate",
    "QqMemberUpdate",
    "QqTestSendRequest",
]
