# Phases 3.3A–3.3B: code chunk storage and automatic persistence

Revision `20261026_0004` enables `vector` and creates `code_chunks`. Existing tables and revisions are unchanged. `app.db.models.CodeChunk` is the ORM model; `app.schemas.chunking.CodeChunk` remains the immutable chunk output contract. The ingestion service now calls `chunk_source` after blob integrity verification; DB persistence validates repository, commit and path against the referenced file and maps every chunk field. Embeddings and search remain unimplemented.

Rows have UUID primary keys, unique stable chunk IDs, cascading repository/file foreign keys, repository/commit/path and file-ID indexes, timestamps and validated line/offset/strategy fields. All chunk output fields are retained, including context and chunker version. Source files remain optional in `repository_files`; this table holds chunk excerpts. Nullable embeddings use `vector(EMBEDDING_DIMENSION)`, default 384. No vector search index is added yet.

`VectorSettings` reads the same environment/.env convention as backend settings without requiring database credentials to import models. Set `EMBEDDING_DIMENSION` before the first upgrade and use the same value for migration and runtime. This is a schema choice, not a per-request option: changing it after installation does not alter the database and requires a new migration and a plan for existing vectors. Retain the chosen value for fresh database provisioning. Upgrade requires permission to create the extension. Downgrade drops chunk data but deliberately retains the potentially shared extension.

Owner-run PowerShell (not executed by the agent):

```powershell
cd C:\Users\HP\Desktop\RepoIQ\backend
uv sync --locked
$env:EMBEDDING_DIMENSION = '384'
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```

Use the existing pooled `DATABASE_URL` and direct `DIRECT_DATABASE_URL`; do not print credentials. In the Neon SQL editor, verify:

```sql
SELECT extversion FROM pg_extension WHERE extname = 'vector';
SELECT format_type(atttypid, atttypmod) AS embedding_type
FROM pg_attribute
WHERE attrelid = 'code_chunks'::regclass AND attname = 'embedding';
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'code_chunks';
```

Expected: extension installed, `vector(384)` (or the configured dimension), unique chunk-ID and lookup indexes; Alembic at `20261026_0004` with no model/schema differences. Tests and migrations: **NOT RUN — owner handles verification**.

## Automatic persistence

Source is fetched by the immutable blob SHA in the saved tree manifest for the job's pinned commit. Pending files are fetched/chunked even if metadata already exists, allowing new jobs to populate chunks for old snapshots. Inserts use stable chunk IDs with `ON CONFLICT DO NOTHING`, in groups of at most 100 rows. Existing embeddings are never overwritten. New embeddings remain NULL; full source is not stored in repository_files.

File metadata, chunks and checkpoint commit in the existing batch transaction. Database failures roll everything back. Parser exceptions and skipped results become terminal per-file ingestion errors (`chunking_failed`/`chunking_skipped`); subsequent files continue. Empty results succeed with zero chunks; labelled text fallbacks are persisted. Existing fetch retries, byte/file limits, locks, cancellation windows and restart recovery remain in effect. Chunking uses its existing source/node/chunk limits; the worker checks the batch deadline between files, not during a native parse.

Already processed checkpoints are not rewound. Start a new ingestion job for the same commit to backfill previously completed files. Changed chunker versions may add distinct chunk IDs; obsolete-version cleanup is outside this phase.

Manual verification after revision 0004 is installed and the API is running:

```powershell
cd C:\Users\HP\Desktop\RepoIQ\backend
$body = @{url='https://github.com/psf/requests'; batch_size=5} | ConvertTo-Json
$job = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/repositories/ingest -ContentType application/json -Body $body
uv run python -m app.workers.ingestion
# In another terminal, poll the returned job ID; stop/restart the worker to inspect recovery.
```

In Neon, inspect metadata and nullable embeddings, and verify duplicates/mismatches are absent:

```sql
SELECT file_path, symbol_name, strategy, commit_sha, embedding IS NULL AS pending_embedding
FROM code_chunks ORDER BY created_at DESC LIMIT 20;
SELECT chunk_id, count(*) FROM code_chunks GROUP BY chunk_id HAVING count(*) > 1;
SELECT c.id FROM code_chunks c JOIN repository_files f ON f.id = c.repository_file_id
WHERE c.repository_id <> f.repository_id OR c.commit_sha <> f.commit_sha OR c.file_path <> f.path;
```

Submit a second job with `ref` set to the first job's commit SHA and confirm chunk counts remain unchanged for the same source/parser configuration. Check existing job status/errors endpoints for per-file failures. No tests, workers, migrations or verification commands were run by the agent.

Asaan alfaaz mein: file ke chunks aur progress aik transaction mein save hotay hain; retry par wahi stable ID dobara record nahi banati.
