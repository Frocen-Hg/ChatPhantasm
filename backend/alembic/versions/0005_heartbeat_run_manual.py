"""heartbeat_runs 补 is_manual（区分面板试跑与自动调度）

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-18

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "heartbeat_runs",
        sa.Column("is_manual", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    # SQLite 删列需批处理模式
    with op.batch_alter_table("heartbeat_runs") as batch:
        batch.drop_column("is_manual")
