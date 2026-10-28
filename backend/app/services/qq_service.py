"""兼容层：QQ 功能已插件化（见 `plugins/qq/`），本模块保留原导入路径 `app.services.qq_service`。

新代码请使用：
    from app.plugin_system import get_plugin
    plugin = get_plugin("qq")  # plugin.bridge / plugin.dispatch_proactive
或直接导入插件模块：
    from plugins.qq import service as qq_service
"""

from ..plugin_system import load_all

load_all()

from plugins.qq import service as _plugin_service  # noqa: E402
from plugins.qq.service import *  # noqa: E402,F401,F403

bridge = _plugin_service.bridge
dispatch_proactive = _plugin_service.dispatch_proactive
