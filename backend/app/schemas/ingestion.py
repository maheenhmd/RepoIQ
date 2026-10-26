
from datetime import datetime
from uuid import UUID, uuid4
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.repository import RepositoryPreviewRequest


class BulkIngestRequest(RepositoryPreviewRequest):
    max_files: int = Field(default=5, ge=1, le=10)


class FetchedFileInfo(BaseModel):
    path: str
    size: int
    sha: str


class IngestionIssue(BaseModel):
    path: str
    reason: str


class BulkIngestResponse(BaseModel):
    full_name: str
    total_files: int
    eligible_files: int
    batch_limit: int
    fetched_files: int
    remaining_files: int
    total_bytes: int
    files: list[FetchedFileInfo]
    issues: list[IngestionIssue]
    rate_limited: bool
    saved_to_database: bool


class StartIngestionRequest(RepositoryPreviewRequest):
    # Swagger's generated optional-ref placeholder is a real, invalid Git ref.
    model_config = ConfigDict(json_schema_extra={
        "examples": [{"url": "https://github.com/psf/requests"}],
    })

    request_id: UUID = Field(default_factory=uuid4)
    ref: str | None = Field(
        default=None, min_length=1, max_length=255,
        description="Optional existing branch, tag or commit SHA. Omit or use null for the repository's default branch.",
    )
    batch_size: int | None = Field(default=None, ge=1, le=50)


class IngestionJobResponse(BaseModel):
    id: UUID
    repository_id: UUID
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    commit_sha: str | None
    total_files: int
    discovered_files: int
    processed_files: int
    succeeded_files: int
    failed_files: int
    remaining_files: int
    progress_percent: float
    batch_size: int
    retry_count: int
    next_attempt_at: datetime | None
    rate_limited: bool
    error_summary: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class IngestionErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_path: str | None
    error_type: str
    error_code: str | None
    message: str
    retryable: bool
    attempt_number: int
    created_at: datetime
