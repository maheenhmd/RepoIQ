"""Persist the ingestion manifest and retry schedule.

Revision ID: 20261026_0003
Revises: 20261026_0002
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261026_0003"
down_revision = "20261026_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ingestion_jobs", sa.Column("file_manifest", postgresql.JSONB(), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("batch_size", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("ingestion_jobs", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ingestion_jobs", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint(op.f("ck_ingestion_jobs_ingestion_jobs_batch_limits"), "ingestion_jobs", "batch_size BETWEEN 1 AND 50 AND retry_count >= 0")
    op.create_index("ix_ingestion_jobs_queue", "ingestion_jobs", ["status", "next_attempt_at", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_queue", table_name="ingestion_jobs")
    op.drop_constraint(op.f("ck_ingestion_jobs_ingestion_jobs_batch_limits"), "ingestion_jobs", type_="check")
    for column in ("next_attempt_at", "retry_count", "batch_size", "file_manifest"):
        op.drop_column("ingestion_jobs", column)
