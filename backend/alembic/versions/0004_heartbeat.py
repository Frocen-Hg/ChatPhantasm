"""P3a 心跳表：调度配置 / 执行记录

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-18

新增 heartbeat_jobs（每角色一行调度配置）、heartbeat_runs（执行记录）。
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "heartbeat_jobs",
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("interval_min", sa.Integer(), nullable=False),
        sa.Column("types_json", sa.Text(), nullable=False),
        sa.Column("quiet_hours_json", sa.Text(), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False),
        sa.Column("jitter_ratio", sa.Float(), nullable=False),
        sa.Column("show_monologue", sa.Boolean(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_heartbeat_jobs_next_run_at", "heartbeat_jobs", ["next_run_at"])

    op.create_table(
        "heartbeat_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("output", sa.Text(), nullable=False),
        sa.Column("memory_id", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_heartbeat_runs_character_id", "heartbeat_runs", ["character_id"])
    op.create_index("ix_heartbeat_runs_status", "heartbeat_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_heartbeat_runs_status", table_name="heartbeat_runs")
    op.drop_index("ix_heartbeat_runs_character_id", table_name="heartbeat_runs")
    op.drop_table("heartbeat_runs")
    op.drop_index("ix_heartbeat_jobs_next_run_at", table_name="heartbeat_jobs")
    op.drop_table("heartbeat_jobs")
