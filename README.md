# Chat Phantasm

LLM 角色扮演平台：多角色卡、分层记忆、独立知识库（向量检索），支持外部 API 与本地 Ollama。

当前进度：**P2 完成**（P0 骨架 → P1 分层记忆 → P2 向量记忆与知识库）；下一阶段 P3 心跳 / 自我对话。

## 功能特性

- **多角色卡**：`card_json`（规范字段）+ `ext_json`（模型/记忆/知识库/心跳微调），前端可编辑。
- **流式聊天**：REST text/plain 流，会话与消息持久化（`X-Conversation-Id` 续接）。
- **分层记忆**：L1 最近消息 / L2 滚动摘要 / L3 事实·偏好·关系（LLM 抽取、去重合并、消息溯源、衰减归档）；按 token 预算组装上下文；注入防护（中和伪区块标题）。
- **向量记忆**：ChromaDB 服务模式；检索 = 关键词 × 重要度 × 时间衰减 × 向量相似度；不可达时**静默降级纯 SQL**；支持重建索引。
- **每角色知识库**：txt/md 导入 → Markdown 感知分块 → 异步索引；lore 条目（常驻 / 关键词触发）；双通道注入 `[知识库]`（记忆优先于知识库）；检索预览（命中与预算内注入分离展示）。
- **模型配置**：Provider 管理（OpenAI 兼容 / Ollama）+ 功能位路由（聊天 / 嵌入等不同功能用不同模型/端点）+ 嵌入模型独立配置（DeepSeek 无 embeddings）。

## 项目结构

```
ChatPhantasm/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口（lifespan：建表/seed/启动记忆与知识库 worker）
│   │   ├── config.py          # pydantic-settings（.env 唯一密钥来源）
│   │   ├── db/                # SQLAlchemy async 模型与会话
│   │   ├── api/v1/            # chat / characters / conversations / providers / memory / kb
│   │   ├── services/          # 编排：chat / character / provider / memory / vector / kb
│   │   ├── memory/            # 记忆算法：retriever / extractor / summarizer / sanitize / tokens
│   │   ├── rag/               # 向量库抽象与 Chroma 服务模式实现
│   │   ├── providers/         # LLM 抽象：openai_compat + ollama
│   │   ├── schemas/           # Pydantic DTO
│   │   ├── seed.py            # 幂等种子数据（影子角色 + provider + 功能位路由）
│   │   └── cli.py             # 终端入口（python -m app.cli）
│   ├── alembic/               # 迁移：0001 P0 / 0002 P1 / 0003 P2 知识库
│   └── pyproject.toml
├── frontend/
│   └── src/                   # Vue3 + Vite + TS + Pinia + Router
│       ├── views/             # Chat / Characters / CharacterEdit / MemoryManager / Knowledge / Settings
│       ├── stores/  api/  types/
├── prompts/                   # 系统提示词与记忆抽取/摘要模板
└── docker-compose.yml         # postgres + chroma + backend + frontend
```

## 快速开始（本地）

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt        # 即 pip install -e ./backend

# 向量库（可选；知识库与语义检索需要）
docker compose up -d chroma            # 映射 http://localhost:8001

uvicorn app.main:app --reload          # 后端 http://127.0.0.1:8000

# 前端（另开终端）
cd frontend
npm install
npm run dev                            # http://localhost:5173，已代理 /api

# 终端对话
python -m app.cli
```

- `.env` 必需：`DEEPSEEK_API_KEY`（密钥只存 `.env`，gitignored）。默认模型 `deepseek-v4-pro`。
- **嵌入模型需单独配置**（DeepSeek 无 embeddings 端点）：设置页「功能位模型 → 嵌入」绑定 Ollama `nomic-embed-text`（维度 768）或其他 OpenAI 兼容嵌入端点。
- 默认数据库为本地 SQLite `data.db`；设 `DATABASE_URL=postgresql+asyncpg://...` 可切换 PostgreSQL。
- 回归测试（独立脚本，临时库，不调 LLM）：`python backend/tests/smoke.py`、`test_seed.py`、`test_jobs.py`、`test_migrations.py`、`test_vector.py`、`test_kb.py`；前端 `npm run typecheck`。

## Docker 部署

```bash
cp .env.example .env                   # 填入 DEEPSEEK_API_KEY

docker compose down -v                 # 首次或 schema 变更时清卷（PG/Chroma）
# 国内网络可用镜像源（compose 已接 build.args）：
#   $env:PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
#   $env:NPM_REGISTRY="https://registry.npmmirror.com"
docker compose up -d --build
```

- 前端 http://localhost:5173（nginx 代理 /api → backend）
- 后端 http://localhost:8000（API 文档 `/docs`、`/redoc`）
- Chroma http://localhost:8001（容器内 backend 使用 `CHROMA_URL=http://chroma:8000`）
- 容器内嵌入端点填宿主机 Ollama：`http://host.docker.internal:11434`

## API（/api/v1）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | /characters、/characters/{id} | 角色卡 CRUD |
| POST | /chat | 流式聊天（text/plain，`X-Conversation-Id` 为会话 id） |
| GET | /conversations?character_id= | 会话列表（含消息数/最后消息预览） |
| GET | /conversations/{id}/messages | 会话消息列表 |
| DELETE | /conversations/{id} | 删除会话（含消息/任务） |
| GET/POST | /providers | Provider 列表 / 新增 |
| POST | /providers/test | 连通性测试（`capability=chat/embedding`） |
| GET/PUT/DELETE | /providers/routes[/{capability}] | 功能位模型路由 |
| GET/POST | /memory/characters/{id}/memories | 记忆列表 / 新建 |
| PATCH/DELETE | /memory/memories/{id} | 编辑 / 删除记忆 |
| GET/PATCH | /memory/characters/{id}/state | 内心状态读取 / 编辑 |
| POST | /memory/search、/memory/context-preview | 检索预览 / 上下文组装预览 |
| POST | /memory/characters/{id}/decay、/reindex | 衰减归档 / 重建记忆向量索引 |
| GET/POST | /kb/characters/{id}/documents[/upload] | 知识库文档列表 / 导入（粘贴或 .txt/.md 上传） |
| GET | /kb/documents/{id}/chunks | 分块预览 |
| DELETE/POST | /kb/documents/{id}、/reindex | 删除文档 / 重建索引 |
| GET/POST | /kb/characters/{id}/lore | lore 条目列表 / 新建 |
| PATCH/DELETE | /kb/lore/{id} | 编辑 / 删除 lore |
| POST | /kb/search | 知识库检索预览（双通道命中 + 注入区块） |
| GET | /health | 健康检查 |

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI + SQLAlchemy(async) + SQLite/PostgreSQL + Alembic |
| AI | OpenAI 兼容 API（DeepSeek 等）+ Ollama（本地对话与嵌入） |
| 向量 | ChromaDB（服务模式，每角色 `char{id}_mem` / `char{id}_kb`） |
| 前端 | Vue3 + Vite + TypeScript + Pinia + Vue Router |

## 演进路线

P0 骨架 ✅ → P1 分层记忆 ✅ → P2 向量记忆与知识库 ✅ → P3 心跳 / 自我对话 → P4 角色卡 Schema 兼容 → P5 发布。
