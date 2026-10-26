"""Create repository ingestion foundation.

Revision ID: 20261026_0001
Revises:
Create Date: 2026-10-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20261026_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner", sa.String(length=39), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("github_url", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("primary_language", sa.String(length=100), nullable=True),
        sa.Column("default_branch", sa.String(length=255), nullable=False),
        sa.Column(
            "last_ingested_commit_sha", sa.String(length=64), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_repositories"),
        sa.UniqueConstraint(
            "github_url", name="uq_repositories_github_url"
        ),
        sa.UniqueConstraint(
            "owner", "name", name="uq_repositories_owner_name"
        ),
    )
    op.create_index(
        "ix_repositories_updated_at",
        "repositories",
        ["updated_at"],
        unique=False,
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=9),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("target_ref", sa.String(length=255), nullable=False),
        sa.Column("target_commit_sha", sa.String(length=64), nullable=True),
        sa.Column("resume_cursor", sa.String(length=1000), nullable=True),
        sa.Column(
            "total_files", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "eligible_files", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "attempted_files", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "succeeded_files", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "failed_files", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "attempt_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "rate_limited",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "total_files >= 0 AND eligible_files >= 0 "
            "AND attempted_files >= 0 AND succeeded_files >= 0 "
            "AND failed_files >= 0 AND attempt_count >= 0",
            name="ck_ingestion_jobs_ingestion_jobs_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_ingestion_jobs_ingestion_jobs_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name="fk_ingestion_jobs_repository_id_repositories",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ingestion_jobs"),
    )
    op.create_index(
        "ix_ingestion_jobs_created_at",
        "ingestion_jobs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_jobs_repository_status",
        "ingestion_jobs",
        ["repository_id", "status"],
        unique=False,
    )

    op.create_table(
        "repository_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_job_id", sa.Uuid(), nullable=True),
        sa.Column("path", sa.String(length=1000), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("blob_sha", sa.String(length=64), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "size_bytes >= 0",
            name="ck_repository_files_repository_files_size_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_job_id"],
            ["ingestion_jobs.id"],
            name="fk_repository_files_ingestion_job_id_ingestion_jobs",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            name="fk_repository_files_repository_id_repositories",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_repository_files"),
        sa.UniqueConstraint(
            "repository_id",
            "commit_sha",
            "path",
            name="uq_repository_files_snapshot_path",
        ),
    )
    op.create_index(
        "ix_repository_files_ingestion_job_id",
        "repository_files",
        ["ingestion_job_id"],
        unique=False,
    )
    op.create_index(
        "ix_repository_files_repository_path",
        "repository_files",
        ["repository_id", "path"],
        unique=False,
    )

    op.create_table(
        "ingestion_errors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_job_id", sa.Uuid(), nullable=False),
        sa.Column("repository_file_id", sa.Uuid(), nullable=True),
        sa.Column("file_path", sa.String(length=1000), nullable=True),
        sa.Column("error_type", sa.String(length=100), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "retryable",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "attempt_number", sa.Integer(), server_default="1", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempt_number >= 1",
            name="ck_ingestion_errors_ingestion_errors_attempt_positive",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_job_id"],
            ["ingestion_jobs.id"],
            name="fk_ingestion_errors_ingestion_job_id_ingestion_jobs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_file_id"],
            ["repository_files.id"],
            name="fk_ingestion_errors_repository_file_id_repository_files",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ingestion_errors"),
    )
    op.create_index(
        "ix_ingestion_errors_job_created_at",
        "ingestion_errors",
        ["ingestion_job_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_errors_retryable",
        "ingestion_errors",
        ["retryable"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ingestion_errors_retryable", table_name="ingestion_errors"
    )
    op.drop_index(
        "ix_ingestion_errors_job_created_at", table_name="ingestion_errors"
    )
    op.drop_table("ingestion_errors")
    op.drop_index(
        "ix_repository_files_repository_path", table_name="repository_files"
    )
    op.drop_index(
        "ix_repository_files_ingestion_job_id", table_name="repository_files"
    )
    op.drop_table("repository_files")
    op.drop_index(
        "ix_ingestion_jobs_repository_status", table_name="ingestion_jobs"
    )
    op.drop_index(
        "ix_ingestion_jobs_created_at", table_name="ingestion_jobs"
    )
    op.drop_table("ingestion_jobs")
    op.drop_index("ix_repositories_updated_at", table_name="repositories")
    op.drop_table("repositories")
