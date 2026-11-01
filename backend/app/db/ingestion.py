"""PostgreSQL queue and idempotent ingestion persistence."""

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, defer

from app.db.database import SessionLocal
from app.db.models import CodeChunk, IngestionError, IngestionJob, IngestionJobStatus, Repository, RepositoryFile
from app.schemas.chunking import CodeChunk as ChunkData


ACTIVE = (IngestionJobStatus.QUEUED, IngestionJobStatus.RUNNING)


def embedding_progress(repository_id, model, dimension=768):
    """One snapshot: latest successfully ingested commit and exact encoder identity."""
    with request_session() as session:
        row = session.execute(select(
            Repository.last_ingested_commit_sha,
            func.count(CodeChunk.id),
            func.count(CodeChunk.id).filter(
                CodeChunk.embedding.is_not(None), CodeChunk.embedding_model == model,
                func.vector_dims(CodeChunk.embedding) == dimension),
        ).select_from(Repository).outerjoin(CodeChunk,
            (CodeChunk.repository_id == Repository.id)
            & (CodeChunk.commit_sha == Repository.last_ingested_commit_sha)
        ).where(Repository.id == repository_id)
          .group_by(Repository.id, Repository.last_ingested_commit_sha)).one_or_none()
        if row is None:
            return None
        commit, total, embedded = row
        return {"total_chunks": total, "embedded_chunks": embedded,
                "commit_sha": commit, "embedding_identity": model,
                "indexing_complete": total > 0 and total == embedded}


class JobAccessError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


@contextmanager
def request_session():
    with SessionLocal() as session:
        session.execute(text("SET LOCAL statement_timeout = '5s'"))
        session.execute(text("SET LOCAL lock_timeout = '1s'"))
        yield session


def get_job(session: Session, job_id: UUID, *, lock: bool = False) -> IngestionJob:
    query = select(IngestionJob).where(IngestionJob.id == job_id).options(defer(IngestionJob.file_manifest))
    if lock:
        query = query.with_for_update(nowait=True)
    job = session.scalar(query)
    if job is None:
        raise JobAccessError("Ingestion job not found", 404)
    return job


def enqueue(session: Session, url: str, request_id: UUID, ref: str | None,
            batch_size: int) -> IngestionJob:
    owner, name = url.removeprefix("https://github.com/").lower().split("/")
    session.execute(insert(Repository).values(
        owner=owner, name=name, github_url=f"https://github.com/{owner}/{name}", default_branch=""
    ).on_conflict_do_nothing(index_elements=["owner", "name"]))
    repository = session.scalar(select(Repository).where(Repository.owner == owner, Repository.name == name))
    session.execute(insert(IngestionJob).values(
        id=request_id, repository_id=repository.id, target_ref=ref or "",
        batch_size=batch_size, status=IngestionJobStatus.QUEUED,
    ).on_conflict_do_nothing(index_elements=["id"]))
    job = get_job(session, request_id)
    if job.repository_id != repository.id or (ref is not None and job.target_ref != ref):
        raise JobAccessError("request_id already belongs to another ingestion request", 409)
    session.commit()  # Persist before the HTTP success response is constructed.
    return job


def cancel(session: Session, job_id: UUID) -> IngestionJob:
    job = get_job(session, job_id, lock=True)
    if job.status in ACTIVE:
        job.status = IngestionJobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        job.next_attempt_at = None
    session.commit()
    return job


def list_errors(session: Session, job_id: UUID, offset: int, limit: int) -> list[IngestionError]:
    get_job(session, job_id)
    return list(session.scalars(select(IngestionError).where(
        IngestionError.ingestion_job_id == job_id
    ).order_by(IngestionError.created_at, IngestionError.id).offset(offset).limit(limit)))


@contextmanager
def claim_job():
    # A transaction lock is the lease: PostgreSQL releases it on connection loss.
    # All network work is bounded; no session-level locks (Neon pooler compatible).
    with SessionLocal() as session, session.begin():
        session.execute(text("SET LOCAL statement_timeout = '10s'"))
        session.execute(text("SET LOCAL lock_timeout = '2s'"))
        session.execute(text("SET LOCAL idle_in_transaction_session_timeout = '120s'"))
        job = session.scalar(select(IngestionJob).where(
            IngestionJob.status.in_(ACTIVE),
            or_(IngestionJob.next_attempt_at.is_(None), IngestionJob.next_attempt_at <= func.now()),
        ).order_by(IngestionJob.next_attempt_at.asc().nullsfirst(), IngestionJob.created_at)
          .with_for_update(skip_locked=True).limit(1))
        if job is None:
            yield None
            return
        # Serialize jobs for the same repository, so overlapping snapshots reuse files.
        key = int.from_bytes(job.repository_id.bytes[:8], "big", signed=True)
        if not session.scalar(select(func.pg_try_advisory_xact_lock(key))):
            job.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=2)
            yield None
            return
        repository = session.get(Repository, job.repository_id)
        yield session, job, repository


def existing_file(session: Session, job: IngestionJob, path: str) -> RepositoryFile | None:
    return session.scalar(select(RepositoryFile).where(
        RepositoryFile.repository_id == job.repository_id,
        RepositoryFile.commit_sha == job.target_commit_sha,
        RepositoryFile.path == path,
    ).options(defer(RepositoryFile.content)))


def save_file(session: Session, job: IngestionJob, item: dict, content_hash: str) -> RepositoryFile:
    session.execute(insert(RepositoryFile).values(
        repository_id=job.repository_id, ingestion_job_id=job.id,
        path=item["path"], commit_sha=job.target_commit_sha, blob_sha=item["sha"],
        content_sha256=content_hash, size_bytes=item["size"], content=None,
    ).on_conflict_do_nothing(constraint="uq_repository_files_snapshot_path"))
    return existing_file(session, job, item["path"])


def save_chunks(session: Session, file: RepositoryFile, chunks: tuple[ChunkData, ...]) -> None:
    """Persist bounded inserts in the caller's checkpoint transaction."""
    for chunk in chunks:
        if (chunk.repository_id, chunk.commit_sha, chunk.file_path) != (
                file.repository_id, file.commit_sha, file.path):
            raise ValueError("Chunk does not belong to the referenced file snapshot")
    for start in range(0, len(chunks), 100):
        rows = [dict(asdict(chunk), repository_file_id=file.id)
                for chunk in chunks[start:start + 100]]
        session.execute(insert(CodeChunk).values(rows).on_conflict_do_nothing(
            constraint="uq_code_chunks_chunk_id"))


def record_error(session: Session, job: IngestionJob, error, path: str | None) -> None:
    session.add(IngestionError(
        ingestion_job_id=job.id, file_path=path,
        error_type="github" if error.retryable else "validation",
        error_code=error.code, message=str(error)[:1000],
        retryable=error.retryable, attempt_number=job.retry_count,
    ))
