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

        # 3.5 记忆 API（P1 分层记忆）
        r = client.post(
            f"/api/v1/memory/characters/{new_id}/memories",
            json={"content": "喜欢和角色聊天气", "kind": "preference", "importance": 8},
        )
        check("创建记忆", r.status_code == 200, r.text)
        mid = r.json()["id"] if r.status_code == 200 else None

        r = client.get(f"/api/v1/memory/characters/{new_id}/memories")
        check("记忆列表 200", r.status_code == 200 and len(r.json()) >= 1, r.text)

        r = client.get(f"/api/v1/memory/characters/{new_id}/memories?kind=preference")
        check("记忆按类型过滤", r.status_code == 200 and len(r.json()) >= 1, r.text)

        if mid:
            r = client.patch(f"/api/v1/memory/memories/{mid}", json={"importance": 3})
            check("更新记忆", r.status_code == 200 and r.json()["importance"] == 3, r.text)

        r = client.get(f"/api/v1/memory/characters/{new_id}/state")
        check("角色状态 200", r.status_code == 200 and r.json()["character_id"] == new_id, r.text)

        if mid:
            r = client.delete(f"/api/v1/memory/memories/{mid}")
            check("删除记忆", r.status_code == 200, r.text)

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

        # 6. provider CRUD（含独立嵌入配置）
        r = client.post(
            "/api/v1/providers",
            json={
                "name": "冒烟临时",
                "type": "ollama",
                "base_url": "http://localhost:11434",
                "models": ["smoke-model"],
                "is_default": False,
                "embedding_model": "nomic-embed-text",
                "is_embedding_default": True,
            },
        )
        check("创建 provider", r.status_code == 200, r.text)
        check(
            "provider 携带嵌入配置",
            r.json().get("embedding_model") == "nomic-embed-text"
            and r.json().get("is_embedding_default") is True,
            r.text,
        )
        pid = r.json()["id"]

        # 6.5 功能位路由（capability → provider/model）
        r = client.get("/api/v1/providers/routes")
        caps = {x["capability"] for x in r.json()} if r.status_code == 200 else set()
        check(
            "路由列表含 chat/embedding",
            r.status_code == 200 and {"chat", "embedding"} <= caps,
            r.text,
        )

        r = client.put(
            "/api/v1/providers/routes/chat",
            json={"provider_id": pid, "model": "smoke-model", "params": {"temperature": 0.9}},
        )
        check("绑定 chat 路由", r.status_code == 200 and r.json()["model"] == "smoke-model", r.text)

        r = client.get("/api/v1/providers/routes")
        chat_route = next((x for x in r.json() if x["capability"] == "chat"), {})
        check("chat 路由指向临时 provider", chat_route.get("provider_id") == pid, r.text)

        r = client.delete(f"/api/v1/providers/{pid}")
        check("删除 provider", r.status_code == 200, r.text)

        r = client.get("/api/v1/providers/routes")
        left = [x for x in r.json() if x["provider_id"] == pid]
        check("删除 provider 清理其路由", left == [], r.text)

        # 7. 删除角色（并验证记忆级联清理）
        client.post(f"/api/v1/memory/characters/{new_id}/memories", json={"content": "级联测试"})
        r = client.delete(f"/api/v1/characters/{new_id}")
        check("删除角色", r.status_code == 200, r.text)
        r = client.get(f"/api/v1/memory/characters/{new_id}/memories")
        check("删除角色级联清理记忆", r.status_code == 200 and r.json() == [], r.text)

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