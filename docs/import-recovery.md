# Milestone 5.2A — owner verification

Implementation only. No tests, builds, workers, network requests, installs, migrations
or Git operations were run. No dependencies or schema changes.

Changed files:
- `frontend/src/app/interview/page.tsx`: localStorage import recovery (not answers),
  job-ID resume, actual retry times, file counts and embedding counts. Existing
  interview sessionStorage remains separate. Mounting only reads job status.
- `backend/app/integrations/ingestion_github.py`: one-second sequential pacing,
  bounded secondary-limit response inspection, rate-limit versus access-denied
  distinction, honor server retry deadlines without shortening them.
- `backend/app/services/ingestion.py`: durable rate-limit scheduling, capped
  exponential backoff, stale error clearing after successful work, committed batch logs.
- `backend/app/workers/ingestion.py`: signal/once/failure shutdown reasons.
- `backend/app/workers/embeddings.py`: optional --watch waits 10 seconds when empty;
  original drain-and-exit and --once semantics remain. Model reused between polls.
- `backend/app/db/ingestion.py`: read-only repository embedding totals.
- `backend/app/api/repositories.py`: additive embedding counts/indexing_complete;
  original ready field retains its existing meaning (at least one compatible vector).
- `backend/start-local.ps1`: three separate local processes, logs under a unique
  TEMP directory, child-exit detection and group cleanup; no installation/migration.
- This document: commands, expected behavior and deployment boundaries.

## Lifecycle

Rate limits leave the pending file checkpoint intact and schedule next_attempt_at;
they no longer fail simply because the ordinary transient-error retry limit elapsed.
Ordinary transient failures remain bounded. Permission failures are not rate limits.
Cancellation remains available through the existing ingestion API. Existing terminal
failed jobs are not silently revived: retry import creates a new job. Successful
files and chunk upserts remain atomic with their batch checkpoint. Interruption can
repeat an uncommitted batch; it cannot advance its committed cursor prematurely.

The UI polls serially and pauses after 60 checks; Refresh status resumes. Long pauses
do not cancel PostgreSQL jobs. Browser closure preserves import metadata but not
worker execution. Copy the displayed job UUID for recovery if browser storage is
blocked/cleared. Local storage contains the public URL/job ID, never credentials.
Multiple independent browsers can still intentionally create separate imports.

Readiness counts all repository chunks, without implementing commit-aware caching.
It requires nonzero chunks and all embeddings matching the current model. Empty
repositories cannot start; incompatible old embeddings need a future explicit
reindex workflow (not silently regenerated). Counts are a snapshot, not worker health.

## Exact PowerShell commands

Stop older local backend/worker processes first to avoid duplicate API ports.
With existing dependencies/models and backend environment configured:

```powershell
Set-Location 'C:\Users\HP\Desktop\RepoIQ\backend'
.\start-local.ps1
```

Separate terminal:

```powershell
Set-Location 'C:\Users\HP\Desktop\RepoIQ\frontend'
npm run dev
```

Open http://localhost:3000/interview. Import a public URL, save its displayed job ID,
close and reopen the tab: expect the same job, not a new POST. Inspect counters and
retry timestamp. After ingestion expect actual embedded/total counts, then Ready
for interview only when complete. Try manual Resume with a missing UUID: expect 404.

Optional read-only inspection in another terminal:

```powershell
$jobId = Read-Host 'Displayed ingestion job UUID'
$job = Invoke-RestMethod "http://127.0.0.1:8000/api/repositories/ingest/$jobId"
$job | ConvertTo-Json
Invoke-RestMethod "http://127.0.0.1:8000/api/repositories/$($job.repository_id)/ready"
```

Stop/restart the startup script: committed progress must survive. Its cleanup is
forced process-tree shutdown, exercising rollback/recovery, not graceful draining.
For graceful signal checks, run each worker directly and press Ctrl+C; logs should
show signal reason after the current bounded batch. Never manufacture GitHub rate
limits by flooding requests. On a naturally occurring limit verify next_attempt_at,
unchanged pending checkpoint, and cleared error_summary after a successful retry.
Keep --watch alive before a second import: newly committed chunks should be picked up.

## Production configuration still required

Use separate supervised API/ingestion/embedding services (systemd, Windows service
manager or hosting worker services), restart-on-failure with backoff, graceful
termination timeouts sufficient for CPU batches, installed model cache, secrets,
log retention/rotation and alerting. The local launcher is not a production supervisor
and intentionally stops all its children if one exits. PostgreSQL remains the queue;
no request performs embeddings. Request pacing is per worker, not a distributed
token limiter: start with one ingestion worker for a token. No deployment performed.

Asaan alfaaz mein: browser job ID yaad rakhta hai; asal progress PostgreSQL mein hai.
Worker dobara chale to committed checkpoint se kaam jari hota hai.
