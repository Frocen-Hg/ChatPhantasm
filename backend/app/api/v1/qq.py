import json

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...db.models import Character, Conversation, Message, QqBinding, QqMember, QqReplyLog
from ...db.session import get_db
from ...schemas.qq import (
    QqBindingCreate,
    QqBindingUpdate,
    QqMemberUpdate,
    QqTestSendRequest,
)
from ...services import qq_service

router = APIRouter(prefix="/qq", tags=["qq"])


def _clean_keywords(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if text and text not in out:
            out.append(text[:64])
    return out[:50]


def _clean_tags(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if text and text not in out:
            out.append(text[:32])
    return out[:20]


async def _require_binding(db: AsyncSession, binding_id: int) -> QqBinding:
    binding = await db.get(QqBinding, binding_id)
    if binding is None:
        raise HTTPException(status_code=404, detail="QQ 绑定不存在")
    return binding


async def _binding_out(db: AsyncSession, binding: QqBinding) -> dict:
    character = await db.get(Character, binding.character_id)
    member_count = (
        await db.execute(
            select(func.count(QqMember.id)).where(QqMember.binding_id == binding.id)
        )
    ).scalar_one()
    hour_count, day_count, last_reply_at = await qq_service.reply_stats(db, binding.id)
    connected = (
        qq_service.bridge.is_connected(binding.bot_uin)
        if binding.bot_uin
        else qq_service.bridge.is_connected()
    )
    return {
        "id": binding.id,
        "character_id": binding.character_id,
        "character_name": character.name if character is not None else "",
        "bot_uin": binding.bot_uin,
        "group_id": binding.group_id,
        "group_name": binding.group_name,
        "conversation_id": binding.conversation_id,
        "enabled": binding.enabled,
        "reply_mode": binding.reply_mode,
        "keywords": binding.keywords,
        "reply_probability": binding.reply_probability,
        "min_interval_sec": binding.min_interval_sec,
        "max_replies_per_hour": binding.max_replies_per_hour,
        "max_replies_per_day": binding.max_replies_per_day,
        "debounce_sec": binding.debounce_sec,
        "mention_bypass_cooldown": binding.mention_bypass_cooldown,
        "proactive_enabled": binding.proactive_enabled,
        "group_note": binding.group_note,
        "last_active_at": binding.last_active_at,
        "created_at": binding.created_at,
        "updated_at": binding.updated_at,
        "member_count": int(member_count),
        "hour_replies": int(hour_count),
        "day_replies": int(day_count),
        "last_reply_at": last_reply_at,
        "connected": connected,
    }


def _member_out(member: QqMember) -> dict:
    return {
        "id": member.id,
        "binding_id": member.binding_id,
        "user_id": member.user_id,
        "nickname": member.nickname,
        "card": member.card,
        "display_name": member.card or member.nickname or member.user_id,
        "role": member.role,
        "tags": member.tags,
        "note": member.note,
        "ignored": member.ignored,
        "message_count": member.message_count,
        "last_message_at": member.last_message_at,
    }


def _reply_out(log: QqReplyLog) -> dict:
    return {
        "id": log.id,
        "binding_id": log.binding_id,
        "conversation_id": log.conversation_id,
        "user_id": log.user_id,
        "trigger": log.trigger,
        "message_id": log.message_id,
        "content": log.content,
        "created_at": log.created_at,
    }


@router.get("/status")
async def status(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(QqBinding.id)))).scalar_one()
    enabled = (
        await db.execute(
            select(func.count(QqBinding.id)).where(QqBinding.enabled.is_(True))
        )
    ).scalar_one()
    return {**qq_service.bridge.status(), "bindings": int(total), "enabled_bindings": int(enabled)}


@router.get("/groups")
async def list_groups(bot_uin: str = ""):
    try:
        groups = await qq_service.bridge.list_groups(bot_uin)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return [
        {
            "group_id": str(item.get("group_id") or ""),
            "group_name": str(item.get("group_name") or ""),
            "member_count": item.get("member_count"),
            "max_member_count": item.get("max_member_count"),
        }
        for item in groups
        if item.get("group_id")
    ]


@router.get("/bindings")
async def list_bindings(
    character_id: int | None = None, db: AsyncSession = Depends(get_db)
):
    stmt = select(QqBinding).order_by(QqBinding.created_at.desc())
    if character_id is not None:
        stmt = stmt.where(QqBinding.character_id == character_id)
    bindings = list((await db.execute(stmt)).scalars().all())
    return [await _binding_out(db, b) for b in bindings]


@router.post("/bindings", status_code=201)
async def create_binding(payload: QqBindingCreate, db: AsyncSession = Depends(get_db)):
    character = await db.get(Character, payload.character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    group_id = payload.group_id.strip()
    bot_uin = payload.bot_uin.strip()
    if not group_id:
        raise HTTPException(status_code=400, detail="群号不能为空")
    exists = (
        await db.execute(
            select(QqBinding).where(
                QqBinding.bot_uin == bot_uin, QqBinding.group_id == group_id
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="该账号下已绑定此群")
    binding = QqBinding(
        character_id=payload.character_id,
        bot_uin=bot_uin,
        group_id=group_id,
        group_name=payload.group_name.strip()[:128],
        enabled=payload.enabled,
        reply_mode=payload.reply_mode,
        keywords_json=json.dumps(_clean_keywords(payload.keywords), ensure_ascii=False),
        reply_probability=payload.reply_probability,
        min_interval_sec=payload.min_interval_sec,
        max_replies_per_hour=payload.max_replies_per_hour,
        max_replies_per_day=payload.max_replies_per_day,
        debounce_sec=payload.debounce_sec,
        mention_bypass_cooldown=payload.mention_bypass_cooldown,
        proactive_enabled=payload.proactive_enabled,
        group_note=payload.group_note,
    )
    db.add(binding)
    await db.commit()
    await db.refresh(binding)
    return await _binding_out(db, binding)


@router.get("/bindings/{binding_id}")
async def get_binding(binding_id: int, db: AsyncSession = Depends(get_db)):
    binding = await _require_binding(db, binding_id)
    return await _binding_out(db, binding)


@router.patch("/bindings/{binding_id}")
async def update_binding(
    binding_id: int, payload: QqBindingUpdate, db: AsyncSession = Depends(get_db)
):
    binding = await _require_binding(db, binding_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("character_id") is not None:
        character = await db.get(Character, int(data["character_id"]))
        if character is None:
            raise HTTPException(status_code=404, detail="角色不存在")
    new_group_id = str(data.get("group_id") or binding.group_id).strip()
    new_bot_uin = str(data.get("bot_uin", binding.bot_uin) or "").strip()
    if new_group_id != binding.group_id or (
        data.get("character_id") is not None and int(data["character_id"]) != binding.character_id
    ):
        # 换群/换角色后不复用旧会话，避免把另一群或另一角色的上下文带进来
        binding.conversation_id = None
    if "group_id" in data or "bot_uin" in data:
        duplicate = (
            await db.execute(
                select(QqBinding).where(
                    QqBinding.bot_uin == new_bot_uin,
                    QqBinding.group_id == new_group_id,
                    QqBinding.id != binding.id,
                )
            )
        ).scalar_one_or_none()
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="该账号下已绑定此群")
    for field, value in data.items():
        if value is None:
            continue
        if field == "keywords":
            binding.keywords_json = json.dumps(_clean_keywords(value), ensure_ascii=False)
        elif field == "group_id":
            binding.group_id = new_group_id
        elif field == "bot_uin":
            binding.bot_uin = new_bot_uin
        elif field == "group_name":
            binding.group_name = str(value)[:128]
        elif field == "group_note":
            binding.group_note = str(value)
        else:
            setattr(binding, field, value)
    await db.commit()
    await db.refresh(binding)
    return await _binding_out(db, binding)


@router.delete("/bindings/{binding_id}")
async def delete_binding(binding_id: int, db: AsyncSession = Depends(get_db)):
    binding = await _require_binding(db, binding_id)
    await db.execute(delete(QqMember).where(QqMember.binding_id == binding_id))
    await db.execute(delete(QqReplyLog).where(QqReplyLog.binding_id == binding_id))
    await db.delete(binding)
    await db.commit()
    qq_service.bridge.forget_binding(binding_id)
    return {"ok": True}


@router.get("/bindings/{binding_id}/members")
async def list_members(
    binding_id: int,
    search: str = "",
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    await _require_binding(db, binding_id)
    stmt = select(QqMember).where(QqMember.binding_id == binding_id)
    if search.strip():
        like = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                QqMember.user_id.like(like),
                QqMember.nickname.like(like),
                QqMember.card.like(like),
                QqMember.note.like(like),
                QqMember.tags_json.like(like),
            )
        )
    stmt = stmt.order_by(QqMember.last_message_at.desc(), QqMember.id.desc()).limit(limit)
    members = list((await db.execute(stmt)).scalars().all())
    return [_member_out(m) for m in members]


@router.patch("/members/{member_id}")
async def update_member(
    member_id: int, payload: QqMemberUpdate, db: AsyncSession = Depends(get_db)
):
    member = await db.get(QqMember, member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="群成员不存在")
    data = payload.model_dump(exclude_unset=True)
    if data.get("tags") is not None:
        member.tags_json = json.dumps(_clean_tags(data["tags"]), ensure_ascii=False)
    if data.get("note") is not None:
        member.note = str(data["note"])[:1000]
    if data.get("ignored") is not None:
        member.ignored = bool(data["ignored"])
    await db.commit()
    await db.refresh(member)
    return _member_out(member)


@router.get("/bindings/{binding_id}/replies")
async def list_replies(
    binding_id: int,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    await _require_binding(db, binding_id)
    result = await db.execute(
        select(QqReplyLog)
        .where(QqReplyLog.binding_id == binding_id)
        .order_by(QqReplyLog.id.desc())
        .limit(limit)
    )
    return [_reply_out(log) for log in result.scalars().all()]


@router.post("/bindings/{binding_id}/send")
async def send_test(
    binding_id: int, payload: QqTestSendRequest, db: AsyncSession = Depends(get_db)
):
    binding = await _require_binding(db, binding_id)
    try:
        message_id = await qq_service.bridge.send_test(
            binding, payload.text, at_user_id=payload.at_user_id
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"ok": True, "qq_message_id": message_id}


@router.get("/bindings/{binding_id}/conversation")
async def get_conversation(binding_id: int, db: AsyncSession = Depends(get_db)):
    binding = await _require_binding(db, binding_id)
    if not binding.conversation_id:
        return None
    conversation = await db.get(Conversation, binding.conversation_id)
    if conversation is None:
        return None
    count = (
        await db.execute(
            select(func.count(Message.id)).where(
                Message.conversation_id == conversation.id
            )
        )
    ).scalar_one()
    return {
        "id": conversation.id,
        "title": conversation.title,
        "character_id": conversation.character_id,
        "message_count": int(count),
        "updated_at": conversation.updated_at,
    }


def _check_ws_token(websocket: WebSocket, query_token: str | None) -> bool:
    if not settings.qq_token:
        return True
    auth = websocket.headers.get("authorization") or ""
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    token = token or (query_token or "")
    return token == settings.qq_token


@router.websocket("/ws")
async def qq_ws(websocket: WebSocket, token: str | None = None):
    """NapCat 反向 WebSocket 入口（OneBot 11）。"""
    if not settings.qq_enabled:
        await websocket.close(code=4403)
        return
    if not _check_ws_token(websocket, token):
        await websocket.close(code=4401)
        return
    header_uin = websocket.headers.get("x-self-id") or websocket.query_params.get("self_id") or ""
    await qq_service.bridge.serve(websocket, header_uin)
