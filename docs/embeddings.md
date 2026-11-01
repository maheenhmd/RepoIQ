# Phase 3.3C: local embeddings

`app.services.embeddings.EmbeddingService` lazily loads `nomic-ai/CodeRankEmbed` using Sentence Transformers, with a pinned model/custom-code revision. The [official model card](https://huggingface.co/nomic-ai/CodeRankEmbed) requires `trust_remote_code=True` and a query instruction prefix. `encode_queries` supplies that prefix exactly once via the prompt argument (callers supply unprefixed queries); `encode_code` uses no prefix. Source snippets are input text, never executed. CPU is the default; fused/Flash Attention features are disabled. First use downloads model weights and its pinned Python implementation from Hugging Face; subsequent runs use the local cache. No paid inference API is used.

Settings: `EMBEDDING_MODEL`, `EMBEDDING_REVISION`, `EMBEDDING_DIMENSION=768`, `EMBEDDING_DEVICE=cpu`, `EMBEDDING_BATCH_SIZE=4`, `EMBEDDING_MAX_TOKENS=1024`, `EMBEDDING_MAX_ATTEMPTS=3`, `EMBEDDING_POLL_SECONDS=5`. Supported batch sizes are 4, 8 and 16; use the largest value that fits available RAM and improves measured throughput. The token limit may be raised to the model's 8192 maximum; longer inputs are truncated by the tokenizer. Higher limits increase CPU time/memory. Each service call accepts at most its selected batch size. Vectors must match the configured dimension and contain only finite values. Changing models requires a compatible instruction convention, revision and dimension; settings do not convert existing embeddings.

Migration `20261026_0005` preserves existing vectors in nullable `legacy_embedding` (unconstrained vector type), sets active embeddings to NULL, and fixes the active column at `vector(768)`. Chunk IDs, content and metadata are retained. Old vectors cannot be meaningfully cast/padded into the new model's space. The migration also adds `embedding_model` to record model/revision, token limit and code-input recipe for each new vector. Downgrade refuses to discard active embeddings or non-384 legacy vectors. Previous migrations are unchanged. The table lock may briefly block ingestion during manual migration.

`app.workers.embeddings` claims NULL rows in deterministic order with row locks and `SKIP LOCKED`; it holds those locks for one batch of local inference and persistence. Model initialization happens before locks. The transaction commits vectors and provenance together. Crashes/errors roll back the batch, leaving rows resumable. Existing non-NULL vectors are never overwritten. SIGINT/SIGTERM finish the current batch then stop. Retries use bounded backoff; after the configured number of consecutive failures the process exits nonzero, retaining pending rows. A consistently failing input/configuration must be corrected before restart; no persistent failure queue is added. SQL has a 30-second statement timeout and inference transactions have a 15-minute idle timeout; reduce batch/token limits if CPU inference exceeds this window. Logs contain counts and exception classes, never source/SQL parameters/credentials. Multiple workers may report no claimable rows while other workers hold locks.

The model and schema dimension are validated once per worker process, outside the batch hot path. Each later batch uses one claim/update transaction. The model instance is reused for the entire run. Per-batch logs report committed chunk count, wall-clock seconds, chunks/second and cumulative count; timing includes row claim, inference, flush and commit. `--batch-size` overrides the environment for one run without changing model identity or vector format.

Ingestion and chunking are unchanged. There is no search or interview integration. Legacy embeddings are archival only; model replacement/re-indexing and archival cleanup require a separate explicit operation.

## Owner-run PowerShell

No tests, migrations, model inference or workers were run by the agent. Stop embedding workers before upgrading; restart existing Python processes afterward to load the new code/settings. Existing `.env` files were not modified. The environment override below supersedes an older `.env` dimension of 384.

```powershell
cd C:\Users\HP\Desktop\RepoIQ\backend
uv sync --locked
$env:EMBEDDING_DIMENSION = '768'
$env:EMBEDDING_MODEL = 'nomic-ai/CodeRankEmbed'
$env:EMBEDDING_REVISION = '3c4b60807d71f79b43f3c4363786d9493691f8b1'
$env:EMBEDDING_DEVICE = 'cpu'
uv run alembic upgrade head
uv run alembic current
uv run alembic check
uv run python -m app.workers.embeddings --once
# Continuous worker; Ctrl+C finishes the active batch before stopping:
uv run python -m app.workers.embeddings
```

## Manual CPU batch benchmark

Benchmark on comparable pending chunks and keep model, token limit, machine load and power settings constant. The first command may include model-cache warm-up, so run one untimed warm-up batch first. These commands persist their batches by design; they do not reset or overwrite existing vectors.

```powershell
cd C:\Users\HP\Desktop\RepoIQ\backend
$env:EMBEDDING_DIMENSION = '768'
$env:EMBEDDING_DEVICE = 'cpu'

# Warm model/cache; one atomic batch only.
uv run python -m app.workers.embeddings --once --batch-size 4

# Compare the reported seconds and chunks_per_second values.
uv run python -m app.workers.embeddings --once --batch-size 4
uv run python -m app.workers.embeddings --once --batch-size 8
uv run python -m app.workers.embeddings --once --batch-size 16

# Use the best measured size to drain remaining NULL rows.
$env:EMBEDDING_BATCH_SIZE = '8'
uv run python -m app.workers.embeddings
```

Because each run claims the next pending rows, source lengths can vary. Repeat comparisons across several newly ingested repositories or similarly sized pending groups before choosing a default. If a larger batch approaches the 15-minute transaction limit or causes memory pressure, select the next smaller size.

Use existing runtime `DATABASE_URL` and direct `DIRECT_DATABASE_URL`. In Neon SQL Editor:

```sql
SELECT count(*) AS chunks,
       count(embedding) AS embedded,
       count(*) FILTER (WHERE embedding IS NULL) AS pending,
       count(legacy_embedding) AS preserved_old_vectors
FROM code_chunks;
SELECT vector_dims(embedding) AS dimensions, embedding_model, count(*)
FROM code_chunks WHERE embedding IS NOT NULL
GROUP BY 1, 2;
SELECT chunk_id, count(*) FROM code_chunks GROUP BY chunk_id HAVING count(*) > 1;
```

Expect 768 dimensions, decreasing pending count, unchanged total chunks and no duplicate IDs. Restarting processes resumes NULL rows. Run `--once` again after completion: it should commit zero chunks. For reusable service verification without DB access:

```powershell
uv run python -c 'from app.core.config import get_vector_settings; from app.services.embeddings import EmbeddingService; s=EmbeddingService(get_vector_settings()); print(len(s.encode_code(["def square(x): return x*x"])[0])); print(len(s.encode_queries(["square a number"])[0]))'
```

Asaan alfaaz mein: worker har pending chunk ko 768 numbers mein badalta hai. Save ho chukay vectors dobara process nahi hotay; restart par NULL walay chunks se kaam jari rehta hai.
