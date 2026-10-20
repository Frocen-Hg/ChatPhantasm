# Chat Phantasm

LLM 角色扮演平台：多角色卡、分层记忆、独立知识库（向量检索）、心跳 / 内心独白 / 主动消息、QQ 群聊接入（NapCat / OneBot 11），支持外部 API 与本地 Ollama。

当前进度：**v0.5.0**（P0 骨架 → P1 分层记忆 → P2 向量记忆与知识库 → P3 心跳 / 内心独白 / 主动消息 / WS 推送 → QQ 群聊接入）；下一阶段 P4 角色卡 Schema 兼容。

## 功能特性

- **多角色卡**：`card_json`（规范字段）+ `ext_json`（模型/记忆/知识库/心跳微调），前端可编辑。
- **流式聊天**：REST text/plain 流，会话与消息持久化（`X-Conversation-Id` 续接）。
- **分层记忆**：L1 最近消息 / L2 滚动摘要 / L3 事实·偏好·关系（LLM 抽取、去重合并、消息溯源、衰减归档）；按 token 预算组装上下文；注入防护（中和伪区块标题）。
- **向量记忆**：ChromaDB 服务模式；检索 = 关键词 × 重要度 × 时间衰减 × 向量相似度；不可达时**静默降级纯 SQL**；支持重建索引。
- **每角色知识库**：txt/md 导入 → Markdown 感知分块 → 异步索引；lore 条目（常驻 / 关键词触发）；双通道注入 `[知识库]`（记忆优先于知识库）；检索预览（命中与预算内注入分离展示）。
- **心跳与内心世界**（v0.4.0）：每角色可配心跳（开关/间隔/类型/静默时段/每日上限/抖动，默认关闭）；内心独白写入 L4 private 记忆并更新内心状态（不直接注入对话、经状态成为"潜台词"）；用户久未说话时可按概率主动开口（落消息并进入记忆流水线，离线可回放）。
- **实时推送**（v0.4.0）：WebSocket `/api/v1/ws` 按角色/会话订阅心跳事件；前端断线指数退避重连；聊天页实时呈现「主动开口 / 内心独白」气泡。
- **心跳面板**（v0.4.0）：`/heartbeat` 配置 / 运行记录 / 试跑（试跑不改排程、计入当日次数）；记忆页提供「内心活动时间线」。
- **QQ 群聊接入**（v0.5.0）：NapCat / OneBot 11 反向 WebSocket；群 ↔ 角色绑定，每群一条独立会话；支持仅 @、关键词、概率闲聊、全量四种触发方式；冷却、每小时/每日上限、消息防抖合并；群成员标签与关系备注注入上下文；心跳主动消息可投递到绑定群；管理面板 `/qq`。
- **模型配置**：Provider 管理（OpenAI 兼容 / Ollama）+ 功能位路由（聊天 / 嵌入 / 心跳等不同功能用不同模型/端点，心跳未绑定回落聊天）+ 嵌入模型独立配置（DeepSeek 无 embeddings）。

## 项目结构

```
ChatPhantasm/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口（lifespan：建表/seed/启动记忆、知识库与心跳 worker）
│   │   ├── config.py          # pydantic-settings（.env 唯一密钥来源）
│   │   ├── db/                # SQLAlchemy async 模型与会话
│   │   ├── api/v1/            # chat / characters / conversations / providers / memory / kb / heartbeat / qq / ws
│   │   ├── services/          # 编排：chat / character / provider / memory / vector / kb / heartbeat / qq / ws
│   │   ├── memory/            # 记忆算法：retriever / extractor / summarizer / sanitize / tokens / monologue / proactive
│   │   ├── rag/               # 向量库抽象与 Chroma 服务模式实现
│   │   ├── providers/         # LLM 抽象：openai_compat + ollama
│   │   ├── schemas/           # Pydantic DTO
│   │   ├── seed.py            # 幂等种子数据（影子角色 + provider + 功能位路由）
│   │   └── cli.py             # 终端入口（python -m app.cli）
│   ├── alembic/               # 迁移：0001 P0 / 0002 P1 / 0003 P2 知识库 / 0004 P3 心跳 / 0005 试跑标记
│   └── pyproject.toml
├── frontend/
│   └── src/                   # Vue3 + Vite + TS + Pinia + Router
│       ├── views/             # Chat / Characters / CharacterEdit / MemoryManager / Knowledge / Heartbeat / Qq / Settings
│       ├── stores/  api/  types/
├── prompts/                   # 系统提示词与记忆抽取/摘要/独白/主动消息模板
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
- 回归测试（独立脚本，临时库，不调 LLM）：`python backend/tests/smoke.py`、`test_seed.py`、`test_jobs.py`、`test_migrations.py`、`test_vector.py`、`test_kb.py`、`test_heartbeat.py`、`test_qq.py`；前端 `npm run typecheck`。

### QQ 群聊（NapCat）

1. 启动后端（默认 `http://127.0.0.1:8000`），在 `.env` 可选设置 `QQ_TOKEN`（与 NapCat 的 token 一致；留空表示不校验）。
2. 启动 `NapCat.Shell` 并登录 QQ。仓库已提供 `NapCat.Shell/config/onebot11.json` 模板：反向 WebSocket 指向 `ws://127.0.0.1:8000/api/v1/qq/ws`。若 NapCat 已生成 `onebot11_<QQ号>.json`，请在 WebUI「网络配置」中手动添加同样的 WebSocket 客户端（消息格式 `array`）。
3. 打开前端「QQ 群聊」页：新增绑定，选择角色、填写群号（可点「群列表」从已连接账号拉取）、设置触发方式与频率。
4. 群成员首次发言后会自动出现在「群成员标签」表；可设置标签（如 `朋友`、`管理员`）与关系备注，或勾选「忽略」。
5. 群内所有消息都会写入该绑定专属会话，可在「对话」页查看；机器人回复由 @ / 关键词 / 概率触发，并受冷却与每小时/每日上限约束。
6. 若希望心跳「主动消息」也发到群里：在绑定中勾选「允许心跳主动消息发到此群」，并在心跳面板启用 `proactive`。每轮心跳只投递到角色最近活跃的绑定群，避免多群同时刷屏。

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
| GET/PUT | /heartbeat/characters/{id} | 心跳配置（含 blocked_reason / 今日次数与试跑分解） |
| POST | /heartbeat/characters/{id}/run | 试跑一次（不改排程，标记 is_manual） |
| GET | /heartbeat/characters/{id}/runs | 心跳运行记录 |
| WS | /ws?character_id=&conversation_id=&token= | 心跳事件推送（按角色/会话订阅，ping/pong 保活） |
| GET | /qq/status | NapCat 连接状态 / 绑定统计 |
| GET/POST | /qq/bindings | QQ 群绑定列表 / 新增 |
| GET/PATCH/DELETE | /qq/bindings/{id} | 绑定详情 / 修改频率与触发配置 / 删除 |
| GET | /qq/groups | 通过已连接账号拉取群列表 |
| GET | /qq/bindings/{id}/members | 群成员（标签/印象/忽略）列表 |
| PATCH | /qq/members/{id} | 修改成员标签 / 备注 / 忽略状态 |
| GET | /qq/bindings/{id}/replies | 最近机器人发言记录 |
| POST | /qq/bindings/{id}/send | 发送测试消息 |
| WS | /qq/ws | NapCat OneBot 11 反向 WebSocket（支持 Authorization Bearer token） |
| GET | /health | 健康检查 |

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI + SQLAlchemy(async) + SQLite/PostgreSQL + Alembic |
| AI | OpenAI 兼容 API（DeepSeek 等）+ Ollama（本地对话与嵌入） |
| 向量 | ChromaDB（服务模式，每角色 `char{id}_mem` / `char{id}_kb`） |
| 前端 | Vue3 + Vite + TypeScript + Pinia + Vue Router |

## 演进路线

P0 骨架 ✅ → P1 分层记忆 ✅ → P2 向量记忆与知识库 ✅ → P3 心跳 / 内心独白 / 主动消息 ✅（v0.4.0）→ QQ 群聊接入 ✅（v0.5.0）→ P4 角色卡 Schema 兼容 → P5 发布。
