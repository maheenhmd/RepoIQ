"""Bounded ingestion stages, checkpoints and persisted retry policy."""

import hashlib
from datetime import datetime, timedelta, timezone
from time import monotonic

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.db import ingestion as storage
from app.db.models import IngestionJobStatus as Status
from app.integrations.github_client import GitHubClientError
from app.integrations.ingestion_github import IngestionFetchError, IngestionGitHub, require_sha
from app.schemas.repository import RepositoryFileRequest
from app.services.file_filter import filter_repository_files
from app.services.source_reader import decode_source_file


def utcnow():
    return datetime.now(timezone.utc)


def status_payload(job) -> dict:
    total = job.eligible_files
    processed = job.succeeded_files + job.failed_files
    return {
        "id": job.id, "repository_id": job.repository_id, "status": job.status.value,
        "commit_sha": job.target_commit_sha, "total_files": total,
        "discovered_files": job.total_files, "processed_files": processed,
        "succeeded_files": job.succeeded_files, "failed_files": job.failed_files,
        "remaining_files": max(0, total - processed),
        "progress_percent": round(100 * processed / total, 2) if total else (
            100.0 if job.status == Status.SUCCEEDED else 0.0),
        "batch_size": job.batch_size, "retry_count": job.retry_count,
        "next_attempt_at": job.next_attempt_at, "rate_limited": job.rate_limited,
        "error_summary": job.error_summary, "created_at": job.created_at,
        "started_at": job.started_at, "completed_at": job.completed_at,
    }


def discover(client, repository, job, settings: Settings) -> None:
    tree = client.tree(repository.owner, repository.name, job.target_commit_sha)
    entries = tree.get("tree")
    if tree.get("truncated") or not isinstance(entries, list) or len(entries) > 50000:
        raise IngestionFetchError("Repository tree exceeds complete-discovery limits", code="tree_limit")
    if any(not isinstance(item, dict) for item in entries):
        raise IngestionFetchError("Invalid repository tree")
    job.total_files = sum(item.get("type") == "blob" for item in entries)
    regular = [item for item in entries if item.get("type") == "blob"
               and item.get("mode") in ("100644", "100755")]
    selected = filter_repository_files(regular)
    if len(selected) > settings.ingestion_max_files:
        raise IngestionFetchError("Repository exceeds eligible-file limit", code="file_limit")
    if sum(item["size"] for item in selected) > settings.ingestion_max_bytes:
        raise IngestionFetchError("Repository exceeds total eligible-byte limit", code="size_limit")
    manifest = []
    for item in selected:
        try:
            RepositoryFileRequest.validate_file_path(item["path"])
        except ValueError as exc:
            raise IngestionFetchError("Repository contains an unsupported file path", code="path_limit") from exc
        manifest.append({"path": item["path"], "sha": require_sha(item.get("sha")), "size": item["size"]})
    manifest.sort(key=lambda item: item["path"])
    if len({item["path"] for item in manifest}) != len(manifest):
        raise IngestionFetchError("Duplicate paths in repository tree")
    job.file_manifest = manifest
    job.eligible_files = len(manifest)
    job.resume_cursor = "0"
    job.retry_count = 0


def handle_failure(session, job, error: IngestionFetchError,
                   settings: Settings, path: str | None = None) -> bool:
    """Return True only when a terminal file failure advances the checkpoint."""
    job.retry_count += 1
    storage.record_error(session, job, error, path)
    job.error_summary = str(error)[:1000]
    job.rate_limited = error.code == "rate_limit"
    if error.retryable and job.retry_count < settings.ingestion_max_attempts:
        delay = max(error.retry_after, min(300, 5 * 2 ** (job.retry_count - 1)))
        job.next_attempt_at = utcnow() + timedelta(seconds=delay)
        return False
    if path is None or job.rate_limited:
        # Rate-limit exhaustion fails the job without skipping its pending files.
        job.status = Status.FAILED
        job.completed_at = utcnow()
        job.next_attempt_at = None
        return False
    job.failed_files += 1
    job.attempted_files += 1
    job.resume_cursor = str(int(job.resume_cursor) + 1)
    job.retry_count = 0
    return True


def finish_if_complete(job, repository) -> None:
    if job.file_manifest is None or int(job.resume_cursor or "0") != len(job.file_manifest):
        return
    if job.succeeded_files + job.failed_files != job.eligible_files:
        raise IngestionFetchError("Inconsistent ingestion checkpoint", code="checkpoint")
    job.status = Status.FAILED if job.failed_files else Status.SUCCEEDED
    job.completed_at = utcnow()
    job.next_attempt_at = None
    if job.failed_files:
        job.error_summary = f"Completed with {job.failed_files} failed files"
    else:
        job.error_summary = None
        repository.last_ingested_commit_sha = job.target_commit_sha


def process_files(session, client, repository, job, settings, deadline) -> None:
    cursor = int(job.resume_cursor or "0")
    if not 0 <= cursor <= len(job.file_manifest) or cursor != job.succeeded_files + job.failed_files:
        raise IngestionFetchError("Inconsistent ingestion checkpoint", code="checkpoint")
    used_bytes = 0
    for _ in range(min(job.batch_size, settings.ingestion_batch_size)):
        if monotonic() >= deadline:
            break
        cursor = int(job.resume_cursor or "0")
        if cursor >= len(job.file_manifest):
            break
        item = job.file_manifest[cursor]
        if used_bytes + item["size"] > settings.ingestion_batch_bytes:
            break
        used_bytes += item["size"]
        try:
            existing = storage.existing_file(session, job, item["path"])
            if existing is None:
                data = client.blob(repository.owner, repository.name, item)
                try:
                    document = decode_source_file(data, item["path"], f"{repository.owner}/{repository.name}")
                except GitHubClientError as exc:
                    raise IngestionFetchError(str(exc), code="invalid_content") from exc
                raw = document["content"].encode("utf-8")
                blob_hash = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
                if len(raw) != item["size"] or blob_hash != item["sha"]:
                    raise IngestionFetchError("GitHub blob integrity mismatch")
                storage.save_file(session, job, item, hashlib.sha256(raw).hexdigest())
            elif existing.blob_sha != item["sha"] or existing.size_bytes != item["size"]:
                raise IngestionFetchError("Stored snapshot metadata mismatch", code="snapshot_mismatch")
        except IngestionFetchError as exc:
            if not handle_failure(session, job, exc, settings, item["path"]):
                break
            continue
        job.succeeded_files += 1
        job.attempted_files += 1
        job.resume_cursor = str(cursor + 1)
        job.retry_count = 0
    finish_if_complete(job, repository)


def process_next_job(settings: Settings) -> bool:
    with storage.claim_job() as claimed:
        if claimed is None:
            return False
        session, job, repository = claimed
        job.status = Status.RUNNING
        job.started_at = job.started_at or utcnow()
        job.attempt_count += 1
        job.rate_limited = False
        # Fair scheduling: after this transaction, older due jobs run first.
        job.next_attempt_at = utcnow()
        deadline = monotonic() + settings.ingestion_batch_seconds
        try:
            with IngestionGitHub(settings, deadline) as client:
                if job.target_commit_sha is None:
                    metadata, ref, sha = client.pin(repository.owner, repository.name, job.target_ref)
                    repository.default_branch = metadata["default_branch"]
                    repository.description = str(metadata.get("description") or "")[:10000] or None
                    language = metadata.get("language")
                    repository.primary_language = str(language)[:100] if language else None
                    job.target_ref, job.target_commit_sha = ref, sha
                    job.retry_count = 0
                elif job.file_manifest is None:
                    if job.resume_cursor or job.attempted_files:
                        raise IngestionFetchError("Legacy job has no durable manifest; start a new job", code="legacy_job")
                    discover(client, repository, job, settings)
                    finish_if_complete(job, repository)
                else:
                    process_files(session, client, repository, job, settings, deadline)
        except IngestionFetchError as exc:
            handle_failure(session, job, exc, settings)
        except SQLAlchemyError:
            raise  # Roll back the whole batch; never commit an invalid checkpoint.
        except (ValueError, TypeError, KeyError, AttributeError):
            handle_failure(session, job, IngestionFetchError("Invalid ingestion state or upstream data"), settings)
        if job.status in storage.ACTIVE and job.next_attempt_at <= utcnow():
            # Leave a cancellation window and avoid a busy loop between batches.
            job.next_attempt_at = utcnow() + timedelta(seconds=settings.ingestion_poll_seconds)
        session.flush()
        return True
