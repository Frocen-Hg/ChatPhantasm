"""P1 表结构：分层记忆 / 内心状态 / 功能位路由 / 记忆任务

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14

新增 memories、character_state、model_routes、memory_jobs，
并为 messages 补 meta_json/importance、providers 补 embedding_model/is_embedding_default。
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- P0 既有表补列（server_default 保证旧行有效）---
    op.add_column("messages", sa.Column("meta_json", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("messages", sa.Column("importance", sa.Float(), nullable=False, server_default="0"))
    op.add_column("providers", sa.Column("embedding_model", sa.String(length=128), nullable=True))
    op.add_column(
        "providers",
        sa.Column("is_embedding_default", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # --- 分层记忆 ---
    op.create_table(
        "memories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("layer", sa.String(length=4), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("embedding_id", sa.String(length=64), nullable=True),
        sa.Column("source_start_id", sa.Integer(), nullable=True),
        sa.Column("source_end_id", sa.Integer(), nullable=True),
        sa.Column("visibility", sa.String(length=8), nullable=False),
        sa.Column("last_access_at", sa.DateTime(), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False),
        sa.Column("decay_at", sa.DateTime(), nullable=True),
        sa.Column("meta_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_memories_character_id", "memories", ["character_id"])

    op.create_table(
        "character_state",
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id"), primary_key=True),
        sa.Column("mood", sa.String(length=64), nullable=False),
        sa.Column("arousal", sa.Float(), nullable=False),
        sa.Column("current_focus", sa.String(length=255), nullable=False),
        sa.Column("relationship_json", sa.Text(), nullable=False),
        sa.Column("last_user_at", sa.DateTime(), nullable=True),
        sa.Column("last_beat_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # --- 功能位路由 ---
    op.create_table(
        "model_routes",
        sa.Column("capability", sa.String(length=16), primary_key=True),
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("params_json", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_model_routes_provider_id", "model_routes", ["provider_id"])

    # --- 记忆任务 outbox ---
    op.create_table(
        "memory_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("source_start_id", sa.Integer(), nullable=False),
        sa.Column("source_end_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=False),
        sa.Column("run_after", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_memory_jobs_character_id", "memory_jobs", ["character_id"])
    op.create_index("ix_memory_jobs_status", "memory_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_memory_jobs_status", table_name="memory_jobs")
    op.drop_index("ix_memory_jobs_character_id", table_name="memory_jobs")
    op.drop_table("memory_jobs")
    op.drop_index("ix_model_routes_provider_id", table_name="model_routes")
    op.drop_table("model_routes")
    op.drop_table("character_state")
    op.drop_index("ix_memories_character_id", table_name="memories")
    op.drop_table("memories")
    # SQLite 删列需批处理模式
    with op.batch_alter_table("providers") as batch:
        batch.drop_column("is_embedding_default")
        batch.drop_column("embedding_model")
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("importance")
        batch.drop_column("meta_json")
