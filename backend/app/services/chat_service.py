from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import Character, Conversation, Message, ProviderConfig
from ..providers.base import LLMProvider
from .character_service import compose_system_prompt
from .provider_service import build_provider

HISTORY_LIMIT = 20


async def get_or_create_conversation(
    db: AsyncSession,
    character_id: int,
    conversation_id: int | None = None,
) -> Conversation:
    if conversation_id:
        conv = await db.get(Conversation, conversation_id)
        if conv and conv.character_id == character_id:
            return conv
    conv = Conversation(character_id=character_id, title="新会话")
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def resolve_provider(db: AsyncSession, character: Character) -> tuple[LLMProvider, dict]:
    """按角色 ext.model 覆盖，否则用全局默认 Provider"""
    ext = character.ext
    model_cfg = dict(ext.get("model") or {})

    provider_id = model_cfg.get("provider")
    if provider_id:
        provider = await db.get(ProviderConfig, int(provider_id))
    else:
        result = await db.execute(select(ProviderConfig).where(ProviderConfig.is_default.is_(True)))
        provider = result.scalar_one_or_none()

    if provider is None:
        raise ValueError("没有可用模型 Provider，请先在「设置」中添加并设为默认")

    llm = build_provider(provider)
    model_cfg.setdefault("model", provider.models[0] if provider.models else settings.default_model)
    model_cfg.setdefault("temperature", settings.default_temperature)
    model_cfg.setdefault("max_tokens", settings.default_max_tokens)
    return llm, model_cfg


async def load_history(db: AsyncSession, conversation_id: int, limit: int = HISTORY_LIMIT) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    rows = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in rows]


async def stream_reply(
    db: AsyncSession,
    conversation: Conversation,
    character: Character,
    provider: LLMProvider,
    model_cfg: dict,
    content: str,
) -> AsyncIterator[str]:
    """流式回复：持久化 user/assistant 消息，逐 token 产出"""
    history = await load_history(db, conversation.id, limit=HISTORY_LIMIT - 1)
    messages = [
        {"role": "system", "content": compose_system_prompt(character.card)},
        *history,
        {"role": "user", "content": content},
    ]
    db.add(Message(conversation_id=conversation.id, role="user", content=content))

    parts: list[str] = []
    async for token in provider.chat(
        messages,
        model=model_cfg["model"],
        temperature=model_cfg["temperature"],
        max_tokens=model_cfg["max_tokens"],
    ):
        parts.append(token)
        yield token

    reply = "".join(parts)
    db.add(Message(conversation_id=conversation.id, role="assistant", content=reply))
    await db.commit()