"""P0 冒烟测试：验证建表/seed/核心 API 连通（不调用真实 LLM、无网络请求）

用法（仓库根目录）：
    python backend/tests/smoke.py

退出码：0 = 全部通过；1 = 存在失败。
使用独立临时 SQLite，不污染本地开发数据。
"""
import os
import sys
import asyncio
import tempfile
from pathlib import Path

# 脚本位于 backend/tests/，向上两级即 backend/，保证可直接以脚本方式运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 用独立临时数据库，避免污染本地开发数据（须在 import app 前设置）
_tmp = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(Path(_tmp.name) / 'smoke.db').as_posix()}"

import traceback  # noqa: E402

try:
    from fastapi.testclient import TestClient  # noqa: E402
    from app.main import app  # noqa: E402
    from app.config import ROOT_DIR  # noqa: E402
    from app.db.session import engine  # noqa: E402
except Exception:
    traceback.print_exc()
    sys.exit(1)

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"[PASS] {name}")
    else:
        FAILED += 1
        print(f"[FAIL] {name}  {detail}")


def main() -> None:
    with TestClient(app) as client:
        # 1. 健康检查
        r = client.get("/api/v1/health")
        check("health 返回 200", r.status_code == 200, r.text)
        check("health 内容正确", r.json() == {"status": "ok"}, r.text)

        # 2. 种子数据
        r = client.get("/api/v1/characters")
        check("角色卡列表 200", r.status_code == 200, r.text)
        check("seed 角色已写入", len(r.json()) >= 1, r.text)

        r = client.get("/api/v1/providers")
        check("provider 列表 200", r.status_code == 200, r.text)
        check("seed provider 已写入", len(r.json()) >= 1, r.text)

        # 3. 角色卡 CRUD
        r = client.post(
            "/api/v1/characters",
            json={"card": {"name": "冒烟角色", "personality": "冒烟测试用"}, "ext": {}},
        )
        check("创建角色 200", r.status_code == 200, r.text)
        new_id = r.json()["id"]

        r = client.put(f"/api/v1/characters/{new_id}", json={"card": {"name": "冒烟角色2"}})
        check("更新角色", r.status_code == 200 and r.json()["name"] == "冒烟角色2", r.text)

        r = client.get(f"/api/v1/characters/{new_id}")
        check("读取角色", r.status_code == 200 and r.json()["id"] == new_id, r.text)

        # 4. 聊天错误路径（不触发真实 LLM）
        r = client.post("/api/v1/chat", json={"character_id": 999999, "content": "hi"})
        check("聊天-角色不存在返回 404", r.status_code == 404, r.text)

        r = client.post("/api/v1/chat", json={"character_id": new_id, "content": "   "})
        check("聊天-空消息返回 400", r.status_code == 400, r.text)

        # 5. 会话列表 / 消息 / 删除
        r = client.get("/api/v1/conversations?character_id=1")
        check("会话列表 200", r.status_code == 200, r.text)
        if r.status_code == 200 and r.json():
            cid = r.json()[0]["id"]
            r = client.get(f"/api/v1/conversations/{cid}/messages")
            check("会话消息 200", r.status_code == 200, r.text)
            r = client.delete(f"/api/v1/conversations/{cid}")
            check("删除会话 200", r.status_code == 200, r.text)

        # 6. provider CRUD
        r = client.post(
            "/api/v1/providers",
            json={
                "name": "冒烟临时",
                "type": "ollama",
                "base_url": "http://localhost:11434",
                "models": ["smoke-model"],
                "is_default": False,
            },
        )
        check("创建 provider", r.status_code == 200, r.text)
        pid = r.json()["id"]
        r = client.delete(f"/api/v1/providers/{pid}")
        check("删除 provider", r.status_code == 200, r.text)

        # 7. 删除角色
        r = client.delete(f"/api/v1/characters/{new_id}")
        check("删除角色", r.status_code == 200, r.text)

        # 8. SPA 深链兜底（存在前端构建产物时）
        if (ROOT_DIR / "frontend" / "dist").exists():
            r = client.get("/characters")
            check("SPA 深链兜底 200", r.status_code == 200, r.text)
            check(
                "SPA 兜底返回 html",
                "text/html" in r.headers.get("content-type", ""),
                r.headers.get("content-type", ""),
            )

    # 释放引擎连接，否则 Windows 下临时数据库文件被占用无法删除
    try:
        asyncio.run(engine.dispose())
    except Exception:
        pass
    try:
        _tmp.cleanup()
    except Exception:
        pass
    print(f"\n结果：{PASSED} 通过 / {FAILED} 失败")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()