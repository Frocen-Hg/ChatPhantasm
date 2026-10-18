"""P2b 知识库表：文档 / 分块 / lore / 索引任务

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kb_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_uri", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("visibility", sa.String(length=8), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("chunk_overlap", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kb_documents_character_id", "kb_documents", ["character_id"])
    op.create_index("ix_kb_documents_status", "kb_documents", ["status"])

    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("kb_documents.id"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
        sa.Column("embedding_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kb_chunks_document_id", "kb_chunks", ["document_id"])
    op.create_index("ix_kb_chunks_character_id", "kb_chunks", ["character_id"])

    op.create_table(
        "kb_lore",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("keys_json", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("constant", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("scan_depth", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("visibility", sa.String(length=8), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kb_lore_character_id", "kb_lore", ["character_id"])

    op.create_table(
        "kb_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("kb_documents.id"), nullable=False),
        sa.Column("character_id", sa.Integer(), sa.ForeignKey("characters.id"), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=False),
        sa.Column("run_after", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_kb_jobs_document_id", "kb_jobs", ["document_id"])
    op.create_index("ix_kb_jobs_character_id", "kb_jobs", ["character_id"])
    op.create_index("ix_kb_jobs_status", "kb_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_kb_jobs_status", table_name="kb_jobs")
    op.drop_index("ix_kb_jobs_character_id", table_name="kb_jobs")
    op.drop_index("ix_kb_jobs_document_id", table_name="kb_jobs")
    op.drop_table("kb_jobs")
    op.drop_index("ix_kb_lore_character_id", table_name="kb_lore")
    op.drop_table("kb_lore")
    op.drop_index("ix_kb_chunks_character_id", table_name="kb_chunks")
    op.drop_index("ix_kb_chunks_document_id", table_name="kb_chunks")
    op.drop_table("kb_chunks")
    op.drop_index("ix_kb_documents_status", table_name="kb_documents")
    op.drop_index("ix_kb_documents_character_id", table_name="kb_documents")
    op.drop_table("kb_documents")
