# Chat Phantasm

LLM 角色扮演平台：多角色卡、分层记忆、心跳自我对话、独立知识库（向量检索），支持外部 API 与本地 Ollama。

当前进度：**P0 骨架**（分层后端 + Provider 抽象 + 角色卡 CRUD + REST 流式聊天 + 最小前端）。完整架构见 `docs/ARCHITECTURE.md`。

## 项目结构

```
ChatPhantasm/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口（/api/v1，lifespan 建表+seed）
│   │   ├── config.py          # pydantic-settings（.env 唯一密钥来源）
│   │   ├── db/                # SQLAlchemy async 模型与会话
│   │   ├── api/v1/            # chat / characters / providers 路由
│   │   ├── services/          # 业务编排（chat/character/provider）
│   │   ├── providers/         # LLM 抽象：openai_compat + ollama
│   │   ├── schemas/           # Pydantic DTO
│   │   ├── seed.py            # 幂等种子数据（影子角色 + deepseek provider）
│   │   └── cli.py             # 终端入口（python -m app.cli）
│   ├── alembic/               # 迁移脚手架
│   └── pyproject.toml         # 包定义与依赖
├── frontend/
│   └── src/                   # Vue3 + Vite + TS + Pinia + Router
│       ├── views/             # ChatView / CharactersView / CharacterEditView / SettingsView
│       ├── stores/            # Pinia stores
│       └── api/               # 类型化 API client
├── prompts/phantasm_v1.txt    # 影子角色卡 seed 系统提示词
├── docker-compose.yml         # postgres + backend + frontend
└── docs/ARCHITECTURE.md       # 目标架构设计
```

## 快速开始（本地）

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt        # 即 pip install -e ./backend
python -m app.seed                     # （可选）初始化种子数据，启动时自动执行
uvicorn app.main:app --reload          # 后端 http://127.0.0.1:8000
# 前端（另开终端）
cd frontend
npm install
npm run dev                            # http://localhost:5173，已代理 /api
# 终端对话
python -m app.cli
```

- `.env` 必需：`DEEPSEEK_API_KEY`。密钥只存 `.env`（gitignored）。
- 默认数据库为本地 SQLite `data.db`（零依赖即跑）；设 `DATABASE_URL=postgresql+asyncpg://...` 可切换 PostgreSQL。

## Docker 部署

```bash
cp .env.example .env   # 填入 DEEPSEEK_API_KEY
docker compose up --build
```

- 前端 http://localhost:5173（nginx 代理 /api → backend）
- 后端 http://localhost:8000，API 文档 http://localhost:8000/docs

## API（/api/v1）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /characters | 角色卡列表 |
| POST | /characters | 新建角色卡（card + ext） |
| PUT | /characters/{id} | 更新角色卡 |
| DELETE | /characters/{id} | 删除角色卡 |
| POST | /chat | 流式聊天（text/plain，响应头 X-Conversation-Id 为会话 id） |
| GET | /conversations?character_id= | 会话列表（含消息数/最后消息预览） |
| GET | /conversations/{id}/messages | 会话消息列表 |
| DELETE | /conversations/{id} | 删除会话（含消息） |
| GET | /providers | Provider 列表 |
| POST | /providers | 新增 Provider |
| POST | /providers/test | 连通性测试 |
| GET | /health | 健康检查 |

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI + SQLAlchemy(async) + PostgreSQL/SQLite |
| AI | OpenAI 兼容 API（DeepSeek 等）+ Ollama（本地） |
| 前端 | Vue3 + Vite + TypeScript + Pinia |

## 演进路线

P0 骨架 → P1 分层记忆 → P2 RAG 知识库 → P3 心跳自我对话 → P4 角色卡 Schema 兼容 → P5 发布（详见 `docs/ARCHITECTURE.md`）。