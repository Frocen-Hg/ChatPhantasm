"""QQ 群聊接入：绑定 / 成员标签 / 发言日志

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-20

新增 qq_bindings（群 ↔ 角色/会话/频率配置）、qq_members（群成员标签与备注）、
qq_reply_logs（发言统计与面板回看）。
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "qq_bindings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("bot_uin", sa.String(length=32), nullable=False),
        sa.Column("group_id", sa.String(length=32), nullable=False),
        sa.Column("group_name", sa.String(length=128), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("reply_mode", sa.String(length=16), nullable=False),
        sa.Column("keywords_json", sa.Text(), nullable=False),
        sa.Column("reply_probability", sa.Float(), nullable=False),
        sa.Column("min_interval_sec", sa.Integer(), nullable=False),
        sa.Column("max_replies_per_hour", sa.Integer(), nullable=False),
        sa.Column("max_replies_per_day", sa.Integer(), nullable=False),
        sa.Column("debounce_sec", sa.Float(), nullable=False),
        sa.Column("mention_bypass_cooldown", sa.Boolean(), nullable=False),
        sa.Column("proactive_enabled", sa.Boolean(), nullable=False),
        sa.Column("group_note", sa.Text(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("bot_uin", "group_id", name="uq_qq_bindings_bot_group"),
    )
    op.create_index("ix_qq_bindings_character_id", "qq_bindings", ["character_id"])
    op.create_index("ix_qq_bindings_group_id", "qq_bindings", ["group_id"])

    op.create_table(
        "qq_members",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("binding_id", sa.Integer(), sa.ForeignKey("qq_bindings.id"), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("nickname", sa.String(length=128), nullable=False),
        sa.Column("card", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("tags_json", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("ignored", sa.Boolean(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("binding_id", "user_id", name="uq_qq_members_binding_user"),
    )
    op.create_index("ix_qq_members_binding_id", "qq_members", ["binding_id"])
    op.create_index("ix_qq_members_user_id", "qq_members", ["user_id"])

    op.create_table(
        "qq_reply_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("binding_id", sa.Integer(), sa.ForeignKey("qq_bindings.id"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_qq_reply_logs_binding_id", "qq_reply_logs", ["binding_id"])
    op.create_index("ix_qq_reply_logs_character_id", "qq_reply_logs", ["character_id"])
    op.create_index("ix_qq_reply_logs_created_at", "qq_reply_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_qq_reply_logs_created_at", table_name="qq_reply_logs")
    op.drop_index("ix_qq_reply_logs_character_id", table_name="qq_reply_logs")
    op.drop_index("ix_qq_reply_logs_binding_id", table_name="qq_reply_logs")
    op.drop_table("qq_reply_logs")

    op.drop_index("ix_qq_members_user_id", table_name="qq_members")
    op.drop_index("ix_qq_members_binding_id", table_name="qq_members")
    op.drop_table("qq_members")

    op.drop_index("ix_qq_bindings_group_id", table_name="qq_bindings")
    op.drop_index("ix_qq_bindings_character_id", table_name="qq_bindings")
    op.drop_table("qq_bindings")
