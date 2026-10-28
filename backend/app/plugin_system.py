"""插件系统：扫描仓库根 `plugins/` 目录，加载启用的插件并统一挂载路由与生命周期。

约定：
- 每个插件是 `plugins/<name>/` 包，必须导出 `plugin`（Plugin 实例）。
- `Plugin.name` 用于注册表键；`Plugin.router`（可选）会被挂到 `/api/v1` 下。
- `Plugin.start()` / `Plugin.stop()` 为异步生命周期钩子，由 main.lifespan 调用。
- 启用列表来自 `ENABLED_PLUGINS`（逗号分隔，默认 `qq`）；为空表示全部加载。
- 插件如需自建数据表：必须在模型模块被导入时向 `app.db.base.Base.metadata` 注册，
  且必须提供 Alembic 迁移（迁移的确定性不允许依赖运行时插件开关）。
"""

import importlib
import logging
import sys
from pathlib import Path

from fastapi import APIRouter

from .config import ROOT_DIR, settings

logger = logging.getLogger(__name__)


class Plugin:
    """插件基类。"""

    name: str = ""
    router: APIRouter | None = None

    async def start(self) -> None:
        """应用启动时调用（建表/seed 之前）。"""

    async def stop(self) -> None:
        """应用关闭时调用。"""


_plugins: dict[str, Plugin] = {}
_loading = False


def _plugin_root() -> Path:
    return ROOT_DIR / "plugins"


def _enabled_names() -> set[str]:
    return {name.strip() for name in settings.enabled_plugins.split(",") if name.strip()}


def load_all() -> dict[str, Plugin]:
    """幂等加载全部启用插件；加载过程中重入时返回当前已注册部分。"""
    global _loading
    if _plugins or _loading:
        return _plugins
    _loading = True
    try:
        if str(ROOT_DIR) not in sys.path:
            sys.path.insert(0, str(ROOT_DIR))
        root = _plugin_root()
        if not root.is_dir():
            logger.warning("插件目录不存在：%s", root)
            return _plugins
        enabled = _enabled_names()
        for path in sorted(p for p in root.iterdir() if p.is_dir()):
            if not (path / "__init__.py").exists():
                continue
            if enabled and path.name not in enabled:
                logger.info("跳过未启用的插件：%s", path.name)
                continue
            try:
                module = importlib.import_module(f"plugins.{path.name}")
            except Exception as e:  # noqa: BLE001 单个插件失败不影响其他插件
                logger.warning("插件 %s 导入失败：%s", path.name, e)
                continue
            plugin = getattr(module, "plugin", None)
            if not isinstance(plugin, Plugin):
                logger.warning("插件 %s 未导出 plugin 实例，跳过", path.name)
                continue
            name = plugin.name or path.name
            _plugins[name] = plugin
            logger.info("已加载插件：%s", name)
    finally:
        _loading = False
    return _plugins


def get_plugin(name: str) -> Plugin | None:
    """按名称获取插件（触发加载；未启用则返回 None）。"""
    return load_all().get(name)


async def start_all() -> None:
    for name, plugin in load_all().items():
        try:
            await plugin.start()
        except Exception as e:  # noqa: BLE001
            logger.warning("插件 %s 启动失败：%s", name, e)


async def stop_all() -> None:
    for name, plugin in load_all().items():
        try:
            await plugin.stop()
        except Exception as e:  # noqa: BLE001
            logger.warning("插件 %s 停止失败：%s", name, e)
