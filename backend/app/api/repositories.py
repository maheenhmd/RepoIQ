
from fastapi import APIRouter, HTTPException
from uuid import UUID

from app.schemas.search import SearchRequest, SearchResponse
from app.services.code_search import SearchError, search_repository

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


@router.post('/lookup')
def lookup_repository(payload: RepositoryPreviewRequest):
    from sqlalchemy import select, func
    from app.db.ingestion import request_session
    from app.db.models import Repository
    from sqlalchemy.exc import SQLAlchemyError
    try:
        with request_session() as session:
            repository_id = session.scalar(select(Repository.id).where(
                func.lower(Repository.github_url) == payload.url.lower()))
        if repository_id is None:
            return {'repository_id': None, 'indexing_complete': False}
        return repository_index_ready(repository_id)
    except SQLAlchemyError:
        raise HTTPException(503, 'Repository lookup unavailable') from None


@router.get("/{repository_id}/ready")
def repository_index_ready(repository_id: UUID):
    from app.core.config import get_vector_settings
    from app.services.embeddings import EmbeddingService
    from app.db.ingestion import embedding_progress
    try:
        settings = get_vector_settings()
        # identity is pure metadata; constructing the service does not load a model.
        identity = EmbeddingService(settings).identity
        progress = embedding_progress(repository_id, identity, settings.embedding_dimension)
    except Exception:
        raise HTTPException(503, "Repository readiness unavailable") from None
    if progress is None:
        raise HTTPException(404, "Repository not found")
    return {"repository_id": repository_id, "ready": progress["embedded_chunks"] > 0, **progress}


@router.post("/{repository_id}/search", response_model=SearchResponse)
def search_repository_code(repository_id: UUID, payload: SearchRequest):
    try:
        return search_repository(repository_id, payload.query, payload.top_k)
    except SearchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from None


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
