from typing import Literal

from pydantic import BaseModel, Field

ReplyMode = Literal["mention", "keyword", "ambient", "all"]


class QqBindingCreate(BaseModel):
    character_id: int
    group_id: str = Field(min_length=1, max_length=32)
    bot_uin: str = Field(default="", max_length=32)  # 空=任一已连接账号
    group_name: str = Field(default="", max_length=128)
    enabled: bool = True
    reply_mode: ReplyMode = "mention"
    keywords: list[str] = Field(default_factory=list)
    reply_probability: float = Field(default=0.15, ge=0.0, le=1.0)
    min_interval_sec: int = Field(default=90, ge=0, le=86400)
    max_replies_per_hour: int = Field(default=12, ge=0, le=1000)
    max_replies_per_day: int = Field(default=80, ge=0, le=10000)
    debounce_sec: float = Field(default=3.0, ge=0.5, le=30.0)
    mention_bypass_cooldown: bool = True
    proactive_enabled: bool = False
    group_note: str = ""


class QqBindingUpdate(BaseModel):
    character_id: int | None = None
    group_id: str | None = Field(default=None, min_length=1, max_length=32)
    bot_uin: str | None = Field(default=None, max_length=32)
    group_name: str | None = Field(default=None, max_length=128)
    enabled: bool | None = None
    reply_mode: ReplyMode | None = None
    keywords: list[str] | None = None
    reply_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    min_interval_sec: int | None = Field(default=None, ge=0, le=86400)
    max_replies_per_hour: int | None = Field(default=None, ge=0, le=1000)
    max_replies_per_day: int | None = Field(default=None, ge=0, le=10000)
    debounce_sec: float | None = Field(default=None, ge=0.5, le=30.0)
    mention_bypass_cooldown: bool | None = None
    proactive_enabled: bool | None = None
    group_note: str | None = None


class QqMemberUpdate(BaseModel):
    tags: list[str] | None = None
    note: str | None = None
    ignored: bool | None = None


class QqTestSendRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    at_user_id: str | None = None
