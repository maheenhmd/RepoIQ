# Optional ONNX search reranking

**Superseded search ordering:** the active pipeline now uses independent vector,
keyword and symbol retrieval with RRF, then optional ONNX and a bounded structural
bonus. The older AST tier/ordinal scheme below is historical, not active. See
[current score semantics and evaluation](hybrid-search.md). Provisioning and memory
limits below still apply.

Search preserves repository/model SQL predicates and cosine `similarity`. It starts
with 20 candidates, filters empty/comments/import-only/syntax fragments, deduplicates,
and refills with deterministic SQL pages up to `SEARCH_MAX_CANDIDATES` (100).
At most `RERANKER_TOP_N` filtered candidates are scored. Shortfalls are logged by
count; fewer results are valid when the cap or available evidence is exhausted.
Exact duplicates retain the first cosine-ranked location; near duplicates are
removed only for the same commit/file/symbol with at least eight lines and 95%
line-set overlap. No model-specific or HTTP-specific symbol rules are used.

For implementation intent, a final structural stage orders executable bodies before
neutral evidence, then trivial declarations/stubs and changelogs. Python uses AST
statements; incomplete Python stays neutral. Other languages require symbol metadata
and explicit body operations. Definition/symbol-lookup and documentation queries
retain upstream ordering. Upstream relevance order is preserved within each tier.
For implementation queries `ranking_score` is descending ordinal utility (candidate
count down to 1), representing the final order; it is not a model confidence.
This preference applies only within the bounded retrieved pool and can promote an
unrelated implementation if candidate retrieval is weak; evaluate varied queries.

The existing small intent adjustments remain the fallback. On successful ONNX
inference for other query intents, `ranking_score` is the raw single-label logit, with no
cosine additions, boosts, or sigmoid. These scores are not probabilities or comparable
across fallback/model modes. `similarity` always remains raw cosine. Documentation
is eligible in both modes. Model quality and actual ordering require owner evaluation;
MS MARCO training does not guarantee code relevance or a particular first result.

## Provision explicitly outside serving requests

Verified official artifacts and configuration at revision
`777b2f369bc1c2f850df8bd367ed1654bda4497b`:
https://huggingface.co/cross-encoder/ms-marco-MiniLM-L4-v2/tree/777b2f369bc1c2f850df8bd367ed1654bda4497b/onnx

The repository provides `model_quint8_avx2.onnx` (8-bit CPU AVX2), tokenizer.json,
and a single-logit BERT classifier with padding ID 0. No export is necessary.
Use this artifact on x86 AVX2 hosts. ARM hosts require the supplied ARM64 quantized
variant and separate verification. The service only reads provisioned local files;
it never downloads, exports, or quantizes. No Hugging Face remote code is loaded.

From backend in PowerShell, on the build/development machine only:

```powershell
uv sync --extra reranker
$revision = '777b2f369bc1c2f850df8bd367ed1654bda4497b'
$base = "https://huggingface.co/cross-encoder/ms-marco-MiniLM-L4-v2/resolve/$revision"
New-Item -ItemType Directory -Force models/reranker | Out-Null
Invoke-WebRequest "$base/onnx/model_quint8_avx2.onnx" -OutFile models/reranker/model.onnx
Invoke-WebRequest "$base/tokenizer.json" -OutFile models/reranker/tokenizer.json
$env:RERANKER_ENABLED = 'true'
```

Package only these two artifacts into the deployment build image/artifact, outside
Git; set `RERANKER_PATH` to that read-only directory. This requires no persistent
runtime disk and no network at runtime. Missing/invalid artifacts trigger fallback.
Do not run the provisioning command in an HTTP request or startup hook.

`RERANKER_ENABLED=false` by default. Optional dependencies are CPU `onnxruntime`,
`tokenizers`, `numpy`, `psutil`; the reranker itself imports no torch/transformers.
The existing embedding dependencies remain unchanged, so `uv sync` can still install
PyTorch for CodeRankEmbed. This is **not** a framework-free complete search deployment.

## Memory and concurrency

One process caches one lazy session and tokenizer. A nonblocking lock protects both
initialization and inference; concurrent requests use fallback. CPU threads=1,
batch=1 (maximum 4), length=256 (maximum 512), candidate count<=40, document input
<=16000 characters. Query input<=2000 characters. FastAPI's existing synchronous
route executes in its thread pool, not on the async event loop.

Before loading and every batch, RSS/system memory and Linux cgroup v1/v2 usage are
checked against the configured 512 MB budget and container limit. Loading reserves
220 MB by default; batches reserve at least 64 MB. Low headroom causes fallback;
load/inference errors disable the reranker until restart and log only exception type.
Use one Uvicorn worker; multiple workers duplicate models. These checks are estimates,
not allocation limits: OS OOM kills cannot be caught. Keep reranking disabled on
Render Free until end-to-end peak memory and concurrent requests are measured.

**Unresolved deployment constraint:** existing CodeRankEmbed query encoding already
loads Sentence Transformers/PyTorch in the API. Preserving that encoder prevents a
credible 512 MB stability guarantee. Disabling this reranker cannot cure encoder OOM.
A separately approved embedding hosting/export design or larger memory budget is
needed before declaring the full API suitable for Render Free. No measurements,
tests, downloads, installs, inference, or API requests were run for this change.

Manual verification after provisioning and starting the API yourself:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/repositories/$repositoryId/search" -ContentType application/json -Body '{"query":"How are HTTP errors handled?","top_k":5}'
```

Compare enabled/disabled results, inspect `similarity` vs `ranking_score`, and repeat
with documentation queries and missing artifacts. Existing checks:
`uv run pytest tests/test_code_search.py -q` (not executed by agent).
