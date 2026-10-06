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