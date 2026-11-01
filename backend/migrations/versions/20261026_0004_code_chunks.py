"""Enable pgvector and persist code chunks.

Revision ID: 20261026_0004
Revises: 20261026_0003
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

from app.core.config import get_vector_settings

revision = "20261026_0004"
down_revision = "20261026_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Dimension is fixed when installed. Keep this setting identical in runtime.
    dimension = get_vector_settings().embedding_dimension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "code_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("repository_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", sa.String(64), nullable=False),
        sa.Column("commit_sha", sa.String(64), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("symbol_name", sa.Text(), nullable=False),
        sa.Column("symbol_type", sa.String(32), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column("strategy", sa.String(16), nullable=False),
        sa.Column("chunker_version", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(dimension), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_code_chunks")),
        sa.UniqueConstraint("chunk_id", name="uq_code_chunks_chunk_id"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE", name=op.f("fk_code_chunks_repository_id_repositories")),
        sa.ForeignKeyConstraint(["repository_file_id"], ["repository_files.id"], ondelete="CASCADE", name=op.f("fk_code_chunks_repository_file_id_repository_files")),
        sa.CheckConstraint("start_line >= 1 AND end_line >= start_line", name=op.f("ck_code_chunks_code_chunks_lines_valid")),
        sa.CheckConstraint("start_offset >= 0 AND end_offset > start_offset AND chunk_index >= 0", name=op.f("ck_code_chunks_code_chunks_offsets_valid")),
        sa.CheckConstraint("strategy IN ('ast', 'tree_sitter', 'text')", name=op.f("ck_code_chunks_code_chunks_strategy_valid")),
    )
    op.create_index("ix_code_chunks_repository_commit_file", "code_chunks", ["repository_id", "commit_sha", "file_path"])
    op.create_index("ix_code_chunks_repository_file_id", "code_chunks", ["repository_file_id"])


def downgrade() -> None:
    op.drop_table("code_chunks")
    # Retain vector: other tables/applications may depend on the extension.

