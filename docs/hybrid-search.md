# Hybrid search and evaluation

Independent PostgreSQL rankings: pgvector cosine, English full-text keyword search
over symbol/path/content, and exact case-sensitive qualified/leaf symbol matching.
Each SQL branch uses the same repository ID, embedding model and non-NULL embedding
predicates. Keyword terms are bound parameters, split from prose/identifiers with
OR matching and English stop-word handling. Exact symbol matching uses query tokens,
not HTTP-specific rules. Every candidate carries its actual cosine similarity.

Each branch returns up to SEARCH_MAX_CANDIDATES (100, cap 200), rather than repeatedly
refetching vector pages. RRF sums 1/(SEARCH_RRF_K + rank) for each unique chunk in each
independent list. No cosine, FTS rank or model logit values are added together.
The union is filtered and deduplicated in RRF order, then the first RERANKER_TOP_N
(20 by default) pass through the optional existing ONNX reranker. A missing/failed
reranker leaves RRF scores in place. Filter shortfalls remain logged by count.

The aggressive AST tier/ordinal override is removed from the active pipeline.
Implementation intent can add only a small bounded structural bonus to executable
bodies: 0.0002 in RRF units or 0.1 in cross-encoder logit units, independently tunable.
This can reorder near ties, not force implementations over arbitrarily better matches.
Definition/documentation/symbol-lookup queries receive no structural adjustment.
ranking_score is the final numeric RRF or logit score plus this optional bonus;
similarity stays raw cosine. Score scales are not comparable across modes. Set
SEARCH_STRUCTURE_ENABLED=false for an ablation. Keyword and symbol branches also
have independent enable flags. No embeddings, ingestion or API schemas change.

No migration is required. FTS and leaf-symbol expressions are computed on demand;
large repositories may need measured expression/GIN indexes in a later migration.
Queries retain the existing five-second statement timeout; timeout fails safely
rather than silently claiming hybrid results. Existing 512 MB embedding limitations
and optional reranker provisioning are documented in search-reranking.md.

## Owner-run evaluation (not executed)

From backend, against an already-running API and an ingested/embedded psf/requests:

```powershell
uv run python scripts/evaluate_search.py --repository-id YOUR-REPOSITORY-UUID
```

The 18 default judgments cover implementation, definition, documentation and symbols.
They are seed judgments, not a verified benchmark: confirm that expected symbols and
README/HISTORY chunks exist in your pinned corpus. Missing documents count as misses;
do not silently omit them. Use --cases PATH.json to supply reviewed judgments for
another repository/commit. Record repository commit and active settings with results.
Expected entries are distinct relevant targets (symbol plus optional path suffix).
Recall@5 measures the fraction of targets found, not duplicate matching chunks;
MRR@5 is reciprocal rank of the first relevant result, zero if absent. API failures
count as zero and are reported separately. Metrics are macro-averaged overall and by
intent. Compare semantic-only, hybrid without reranking, and full pipeline on the same
judgments; no first-place result is guaranteed. No tests/scripts/API calls were run.
