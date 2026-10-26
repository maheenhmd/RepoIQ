
from pydantic import BaseModel, Field

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
