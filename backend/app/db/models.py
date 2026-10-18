# 数据模型

import json
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(16), default="1")
    card_json: Mapped[str] = mapped_column(Text)  # 规范化角色卡 JSON
    ext_json: Mapped[str] = mapped_column(Text, default="{}")  # 扩展配置(模型/记忆/心跳/知识库)
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    @property
    def card(self) -> dict:
        return json.loads(self.card_json or "{}")

    @property
    def ext(self) -> dict:
        return json.loads(self.ext_json or "{}")


class ProviderConfig(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(16))  # openai_compat | ollama
    base_url: Mapped[str] = mapped_column(String(255), default="")
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    models_json: Mapped[str] = mapped_column(Text, default="[]")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)  # 聊天默认
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)  # 嵌入模型，独立于聊天模型
    is_embedding_default: Mapped[bool] = mapped_column(Boolean, default=False)  # 嵌入默认
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    @property
    def models(self) -> list[str]:
        try:
            return json.loads(self.models_json or "[]")
        except json.JSONDecodeError:
            return []


class ModelRoute(Base):
    """功能位 → 模型路由：capability(chat/embedding/...) 绑定某个 Provider 与模型。

    把「连接凭证」与「功能位用哪个模型」解耦：一个 Provider 可被多个功能位复用，
    同一 Provider 的不同功能位可用不同模型。
    """

    __tablename__ = "model_routes"

    capability: Mapped[str] = mapped_column(String(16), primary_key=True)  # chat | embedding | ...
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), index=True)
    model: Mapped[str] = mapped_column(String(128), default="")
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    @property
    def params(self) -> dict:
        try:
            return json.loads(self.params_json or "{}")
        except json.JSONDecodeError:
            return {}


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"))
    title: Mapped[str] = mapped_column(String(128), default="新会话")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(16))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    meta_json: Mapped[str] = mapped_column(Text, default="{}")  # 情绪/标签等附加信息
    importance: Mapped[float] = mapped_column(Float, default=0.0)  # 消息级重要度（预留）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class Memory(Base):
    """统一分层记忆：layer 定层，kind 定类型（记忆/知识/内心在数据层分离）"""

    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"), nullable=True)
    layer: Mapped[str] = mapped_column(String(4))  # L2 情节 | L3 长期 | L4 内心
    kind: Mapped[str] = mapped_column(String(16))  # summary | fact | preference | relation | episode | monologue | reflection
    content: Mapped[str] = mapped_column(Text)
    importance: Mapped[float] = mapped_column(Float, default=5.0)  # 1-10
    embedding_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 向量库 id，P2 使用
    source_start_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 溯源 messages.id
    source_end_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visibility: Mapped[str] = mapped_column(String(8), default="public")  # public | private
    last_access_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    decay_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    meta_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    @property
    def meta(self) -> dict:
        try:
            return json.loads(self.meta_json or "{}")
        except json.JSONDecodeError:
            return {}


class MemoryJob(Base):
    """记忆写入任务（outbox）：与消息同事务落库，由 worker 可靠消费并支持重试。

    避免 asyncio.create_task 在进程重启/CLI 退出时静默丢失抽取与摘要。
    """

    __tablename__ = "memory_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    source_start_id: Mapped[int] = mapped_column(Integer)  # user 消息 id
    source_end_id: Mapped[int] = mapped_column(Integer)  # assistant 消息 id
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending|running|done|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    run_after: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class KbDocument(Base):
    """知识库文档：SQL 为唯一事实源（分块持久化），向量库只是索引"""

    __tablename__ = "kb_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), index=True)
    title: Mapped[str] = mapped_column(String(128), default="未命名文档")
    source_type: Mapped[str] = mapped_column(String(16), default="text")  # text | file
    source_uri: Mapped[str] = mapped_column(String(255), default="")  # 文件名（溯源/展示）
    scope: Mapped[str] = mapped_column(String(16), default="world")  # world|self|relation|rule
    visibility: Mapped[str] = mapped_column(String(8), default="public")  # public|private
    chunk_size: Mapped[int] = mapped_column(Integer, default=800)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending|indexed|failed
    error: Mapped[str] = mapped_column(Text, default="")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("kb_documents.id"), index=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)  # 文档内序号
    content: Mapped[str] = mapped_column(Text)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    embedding_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 向量库 id
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class KbLore(Base):
    """lore 条目（World Info 风格）：关键词触发 / 常驻注入"""

    __tablename__ = "kb_lore"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), index=True)
    keys_json: Mapped[str] = mapped_column(Text, default="[]")  # 触发关键词
    content: Mapped[str] = mapped_column(Text)
    constant: Mapped[bool] = mapped_column(Boolean, default=False)  # 常驻注入
    priority: Mapped[int] = mapped_column(Integer, default=0)  # 越大越靠前
    scan_depth: Mapped[int] = mapped_column(Integer, default=6)  # 只扫最近 N 条消息
    scope: Mapped[str] = mapped_column(String(16), default="world")
    visibility: Mapped[str] = mapped_column(String(8), default="public")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    @property
    def keys(self) -> list[str]:
        try:
            return [str(k) for k in json.loads(self.keys_json or "[]")]
        except json.JSONDecodeError:
            return []


class KbJob(Base):
    """知识库索引任务（outbox）：与文档同事务落库，由 kb worker 可靠消费"""

    __tablename__ = "kb_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("kb_documents.id"), index=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    run_after: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class HeartbeatJob(Base):
    """心跳调度配置（每角色一行，P3a）：worker 扫描到期行执行独白/主动消息。

    语义：next_run_at 为下次计划时间，每次运行后按 interval × 抖动推进；
    静默时段与每日上限在扫描时过滤（不推进 next_run_at，解禁后自然触发）。
    """

    __tablename__ = "heartbeat_jobs"

    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_min: Mapped[int] = mapped_column(Integer, default=60)
    types_json: Mapped[str] = mapped_column(Text, default='["monologue","proactive"]')
    quiet_hours_json: Mapped[str] = mapped_column(Text, default='{"start":"23:00","end":"08:00"}')
    daily_limit: Mapped[int] = mapped_column(Integer, default=12)  # 0 表示不运行
    jitter_ratio: Mapped[float] = mapped_column(Float, default=0.2)  # 抖动比例，避免整点齐发
    show_monologue: Mapped[bool] = mapped_column(Boolean, default=False)  # 前端是否展示独白（不影响注入）
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    @property
    def types(self) -> list[str]:
        try:
            return [str(t) for t in json.loads(self.types_json or "[]")]
        except json.JSONDecodeError:
            return []

    @property
    def quiet_hours(self) -> dict:
        try:
            data = json.loads(self.quiet_hours_json or "{}")
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}


class HeartbeatRun(Base):
    """心跳执行记录（P3a）：每次独白/主动消息一行，供面板回看与失败排查"""

    __tablename__ = "heartbeat_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), index=True)
    conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(16))  # monologue | proactive
    status: Mapped[str] = mapped_column(String(16), default="running", index=True)  # running | done | failed
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False)  # True=面板试跑，False=调度自动触发
    output: Mapped[str] = mapped_column(Text, default="")  # 生成的文本（面板回看）
    memory_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 独白对应的 memories.id
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 主动消息对应的 messages.id
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CharacterState(Base):
    """角色内心状态（单行），供独白/心跳读写；P1 仅建表，P3 填充"""

    __tablename__ = "character_state"

    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), primary_key=True)
    mood: Mapped[str] = mapped_column(String(64), default="")
    arousal: Mapped[float] = mapped_column(Float, default=0.0)
    current_focus: Mapped[str] = mapped_column(String(255), default="")
    relationship_json: Mapped[str] = mapped_column(Text, default="{}")
    last_user_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_beat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    @property
    def relationship(self) -> dict:
        try:
            return json.loads(self.relationship_json or "{}")
        except json.JSONDecodeError:
            return {}