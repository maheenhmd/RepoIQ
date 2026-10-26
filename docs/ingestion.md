# Automatic repository ingestion

Implementation only: tests, migrations, API/worker startup and runtime verification have NOT RUN.

## Start locally (PowerShell)

Use the existing backend `.env` with pooled `DATABASE_URL` and direct `DIRECT_DATABASE_URL`. Do not copy the example over existing credentials. `GITHUB_TOKEN` is optional; only public repositories are accepted even when a token can access private ones.

```powershell
cd C:\Users\HP\Desktop\RepoIQ\backend
uv sync
uv run alembic upgrade head
uv run alembic current
uv run alembic check
uv run uvicorn app.main:app --reload
```

In a second PowerShell terminal:

```powershell
cd C:\Users\HP\Desktop\RepoIQ\backend
uv run python -m app.workers.ingestion
```

`uv run python -m app.workers.ingestion --once` processes at most one due stage/batch and exits, for scheduled execution. A single invocation does not finish a repository. Automatic production ingestion requires a continuously running worker or recurring execution. Neon does not run the worker; free/serverless HTTP hosting does not guarantee an always-running process. One worker is a reasonable starting point for limited Neon connections. Multiple workers safely skip locked jobs, but each active batch occupies a database connection.

## Manual verification

In a third PowerShell terminal, submit once. Save the returned ID to recover progress after restarting a terminal or process.

```powershell
$base = 'http://127.0.0.1:8000/api/repositories/ingest'
$requestId = [guid]::NewGuid().ToString()
$body = @{ url = 'https://github.com/psf/requests'; batch_size = 5; request_id = $requestId } | ConvertTo-Json
$job = Invoke-RestMethod -Method Post -Uri $base -ContentType 'application/json' -Body $body
$jobId = $job.id
$job
Invoke-RestMethod -Uri "$base/$jobId"
Invoke-RestMethod -Uri "$base/$jobId/errors?offset=0&limit=20"
```

Expect 202 with a queued job immediately, then progress without further POST requests. Counts are zero until discovery is committed. `total_files` means eligible files; `discovered_files` includes excluded blobs. `processed_files = succeeded_files + failed_files`. A failed job may have remaining files. A job that processed every candidate but had file failures reports failed with 100% progress. A successfully discovered empty eligible set succeeds with 100% progress.

Optional status polling is read-only and does not schedule or execute ingestion:

```powershell
do {
    $state = Invoke-RestMethod -Uri "$base/$jobId"
    $state | Select-Object status,commit_sha,processed_files,failed_files,remaining_files,progress_percent,next_attempt_at
    if ($state.status -in @('queued','running')) { Start-Sleep -Seconds 3 }
} while ($state.status -in @('queued','running'))
Invoke-RestMethod -Uri "$base/$jobId/errors?offset=0&limit=100"
```

Repeat the original POST with the same `$body`: it must return the same job ID, including after completion. Reusing a request_id for another repository/ref returns 409. Omitting request_id creates a fresh ID on each submission. To retry a terminal failed job, submit a new request_id and `ref` equal to its `commit_sha`; already saved snapshot files will be reused. Failed jobs do not resume automatically forever.

Crash recovery: stop the worker during a large job, leave the API running, then restart the same worker command. Polling alone must not advance progress while no worker runs. The previous transaction either committed atomically or rolls back; the next worker resumes the last committed checkpoint. With a lost network connection, release may wait for PostgreSQL to detect disconnect or the configured 120-second idle transaction timeout. Abruptly interrupted fetches may be repeated; successful database records are not duplicated. Running a second worker must not double-count the same job's files.

Cancellation:

```powershell
Invoke-RestMethod -Method Post -Uri "$base/$jobId/cancel"
```

An active locked batch returns 409 with Retry-After; retry between batches. The worker leaves an `INGESTION_POLL_SECONDS` pause between successful batches. Cancellation keeps already saved files and errors. Cancelling an already terminal job returns its unchanged status.

Legacy preview remains available:

```powershell
Invoke-RestMethod -Method Post -Uri "$base/preview" -ContentType 'application/json' -Body '{"url":"https://github.com/psf/requests","max_files":5}'
```

## Limits and recovery semantics

- Settings in `.env.example`: `INGESTION_BATCH_SIZE=10`, `INGESTION_BATCH_BYTES=524288`, `INGESTION_BATCH_SECONDS=20`, `INGESTION_MAX_FILES=10000`, `INGESTION_MAX_BYTES=52428800`, `INGESTION_MAX_ATTEMPTS=3`, `INGESTION_POLL_SECONDS=2`. Environment variables override defaults. A requested batch_size is capped by the worker's configured batch size.
- Each file remains subject to the existing 200 KiB limit and filtering. Symlinks/submodules, invalid paths, excluded directories and likely secret filenames are excluded or rejected. Text is decoded as UTF-8 and checked against the pinned blob's Git SHA; SHA-256 and metadata are saved, never source text. File filtering is a safeguard, not a comprehensive secret scanner.
- Full discovery is bounded to an 8 MiB response and 50,000 tree entries. Truncated trees and repositories exceeding eligible file/byte limits fail explicitly. Large repositories are not silently marked complete. Limits are applied during discovery; changing total limits affects new discoveries, while existing jobs retain their saved manifest. Network operations have a 5-second timeout and a batch deadline; an in-flight read/connection may take up to its timeout beyond that deadline. Database statement/lock timeouts also bound waits.
- Each failed operation is attempted at most `INGESTION_MAX_ATTEMPTS` times across worker runs. Retry delays are 5, 10, ... seconds (capped at 300), or at least GitHub Retry-After/reset when rate-limited (bounded to one day). Errors and retry timestamps are committed. The rate-limit flag denotes the last attempt; it is cleared on the next due attempt. Completed jobs may retain historical retry errors.
- The commit is pinned by the worker before discovery, not at submission time. Every downloaded blob comes from the saved tree at that commit. Eligibility is frozen in the manifest, and processed indexes are committed with their file/error records.
- SQLAlchemy failures roll back the batch; the worker reconnects with capped backoff. No credentials, SQL parameters or source bodies are emitted by worker logging. A database outage cannot itself be durably logged to the unavailable database.
- UUIDs are identifiers, not authorization. These endpoints have no user authentication, per-user quotas or retention policy yet; use locally or behind access controls. No public deployment readiness is claimed. No RAG, embeddings or voice work is included.

## Changed files

Created `app/api/ingestion.py`, `app/db/ingestion.py`, `app/services/ingestion.py`, `app/integrations/ingestion_github.py`, `app/workers/__init__.py`, `app/workers/ingestion.py`, `migrations/versions/20261026_0003_ingestion_queue.py`, and this document.

Updated `app/main.py`, `app/core/config.py`, `app/db/database.py`, `app/db/models.py`, `app/schemas/ingestion.py`, `app/services/source_reader.py`, `.env.example`, `pyproject.toml`, `uv.lock`, `README.md`, `docs/architecture.md`, and `docs/milestones.md`. Backend paths are relative to `backend/`. HTTPX was moved from dev to runtime dependencies; no new library was added. Earlier migrations and real `.env` files are untouched.

Asaan alfaaz mein: API job database mein rakh deti hai. Worker khud batches chalata hai. Har committed batch ka checkpoint bachta hai; restart par wahin se kaam jari hota hai.
