from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class IngestionJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Repository(TimestampMixin, Base):
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint(
            "owner", "name", name="uq_repositories_owner_name"
        ),
        Index("ix_repositories_updated_at", "updated_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner: Mapped[str] = mapped_column(String(39), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    github_url: Mapped[str] = mapped_column(
        String(512), nullable=False, unique=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    primary_language: Mapped[str | None] = mapped_column(String(100))
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    last_ingested_commit_sha: Mapped[str | None] = mapped_column(String(64))

    files: Mapped[list[RepositoryFile]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    ingestion_jobs: Mapped[list[IngestionJob]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class RepositoryFile(TimestampMixin, Base):
    __tablename__ = "repository_files"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "commit_sha",
            "path",
            name="uq_repository_files_snapshot_path",
        ),
        Index("ix_repository_files_repository_path", "repository_id", "path"),
        Index("ix_repository_files_ingestion_job_id", "ingestion_job_id"),
        CheckConstraint(
            "size_bytes >= 0", name="repository_files_size_nonnegative"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    ingestion_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="SET NULL")
    )
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    blob_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)

    repository: Mapped[Repository] = relationship(back_populates="files")
    ingestion_job: Mapped[IngestionJob | None] = relationship(
        back_populates="files"
    )
    ingestion_errors: Mapped[list[IngestionError]] = relationship(
        back_populates="repository_file"
    )


class IngestionJob(TimestampMixin, Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        Index(
            "ix_ingestion_jobs_repository_status",
            "repository_id",
            "status",
        ),
        Index("ix_ingestion_jobs_created_at", "created_at"),
        Index("ix_ingestion_jobs_queue", "status", "next_attempt_at", "created_at"),
        CheckConstraint("batch_size BETWEEN 1 AND 50 AND retry_count >= 0", name="ingestion_jobs_batch_limits"),
        CheckConstraint(
            "total_files >= 0 AND eligible_files >= 0 "
            "AND attempted_files >= 0 AND succeeded_files >= 0 "
            "AND failed_files >= 0 AND attempt_count >= 0",
            name="ingestion_jobs_counts_nonnegative",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ingestion_jobs_status_valid",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[IngestionJobStatus] = mapped_column(
        SqlEnum(
            IngestionJobStatus,
            name="ingestion_job_status",
            native_enum=False,
            create_constraint=False,
            length=9,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=IngestionJobStatus.QUEUED,
        server_default=IngestionJobStatus.QUEUED.value,
    )
    target_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    target_commit_sha: Mapped[str | None] = mapped_column(String(64))
    resume_cursor: Mapped[str | None] = mapped_column(String(1000))
    file_manifest: Mapped[list[dict] | None] = mapped_column(JSONB)
    batch_size: Mapped[int] = mapped_column(Integer, server_default=text("10"), default=10)
    retry_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_files: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    eligible_files: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    attempted_files: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    succeeded_files: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    failed_files: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    rate_limited: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    repository: Mapped[Repository] = relationship(
        back_populates="ingestion_jobs"
    )
    files: Mapped[list[RepositoryFile]] = relationship(
        back_populates="ingestion_job"
    )
    errors: Mapped[list[IngestionError]] = relationship(
        back_populates="ingestion_job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class IngestionError(Base):
    __tablename__ = "ingestion_errors"
    __table_args__ = (
        Index(
            "ix_ingestion_errors_job_created_at",
            "ingestion_job_id",
            "created_at",
        ),
        Index("ix_ingestion_errors_retryable", "retryable"),
        CheckConstraint(
            "attempt_number >= 1",
            name="ingestion_errors_attempt_positive",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ingestion_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="CASCADE"), nullable=False
    )
    repository_file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("repository_files.id", ondelete="SET NULL")
    )
    file_path: Mapped[str | None] = mapped_column(String(1000))
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    retryable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ingestion_job: Mapped[IngestionJob] = relationship(
        back_populates="errors"
    )
    repository_file: Mapped[RepositoryFile | None] = relationship(
        back_populates="ingestion_errors"
    )
