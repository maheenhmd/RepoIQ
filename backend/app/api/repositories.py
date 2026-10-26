
from fastapi import APIRouter, HTTPException

from app.integrations.github_client import GitHubClientError

from app.schemas.repository import (
    RepositoryPreviewRequest,
    RepositoryPreviewResponse,
    RepositoryFileRequest,
    RepositoryFileContentResponse,
)

from app.schemas.ingestion import (
    BulkIngestRequest,
    BulkIngestResponse,
)

from app.services.repo_importer import (
    preview_repository,
    discover_repository_files,
    discover_filtered_repository_files,
)

from app.services.source_reader import fetch_source_file
from app.services.bulk_ingestor import collect_repository_documents


router = APIRouter()


@router.post(
    "/preview",
    response_model=RepositoryPreviewResponse,
)
def preview_github_repository(payload: RepositoryPreviewRequest):
    try:
        return preview_repository(payload.url)
    except GitHubClientError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc


@router.post("/files")
def list_repository_files(payload: RepositoryPreviewRequest):
    try:
        return discover_repository_files(payload.url)
    except GitHubClientError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc


@router.post("/files/filtered")
def list_filtered_files(payload: RepositoryPreviewRequest):
    try:
        return discover_filtered_repository_files(payload.url)
    except GitHubClientError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/file-content",
    response_model=RepositoryFileContentResponse,
)
def read_repository_file(payload: RepositoryFileRequest):
    try:
        return fetch_source_file(payload.url, payload.path)
    except GitHubClientError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc


@router.post(
    "/ingest/preview",
    response_model=BulkIngestResponse,
)
def preview_bulk_ingestion(payload: BulkIngestRequest):
    try:
        summary, _documents = collect_repository_documents(
            payload.url,
            payload.max_files,
        )
        return summary

    except GitHubClientError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc
