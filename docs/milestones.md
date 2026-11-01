# RepoIQ milestone checklist

- [ ] Add GitHub URL validation and metadata import.
- [ ] Filter files and enforce size/security constraints.
- [x] Add the PostgreSQL/Neon ORM foundation and initial Alembic migration (applied to Neon, owner reported).
- [x] Make full source storage optional with revision `20261026_0002` (migration and tests not run).
- [x] Implement automatic, commit-pinned ingestion with a PostgreSQL queue, bounded worker batches, persisted retries, status/errors/cancel APIs and revision `20261026_0003` (not executed or tested).
- [ ] Index the code and implement repository-aware retrieval.
- [x] Implement local CodeRankEmbed service and resumable embedding worker with revision 0005 (Phase 3.3C; tests/migration/inference not run).
- [x] Add pgvector and code chunk persistence schema (Phase 3.3A; migration/tests not run; no indexing integration).
- [x] Implement standalone deterministic Python AST chunking with bounded text fallback (Phase 3.1; tests/runtime verification not run).
- [x] Add hybrid Tree-sitter chunking for JavaScript/JSX, TypeScript/TSX, Java and C# while preserving Python AST behavior (Phase 3.2; tests/runtime verification not run).
- [x] Implement adaptive repository-grounded interviews with local Ollama (Phase 4A; not runtime verified).
- [x] Add qualitative code-backed feedback and dynamic follow-up/topic/finish decisions (mocked tests NOT RUN; advanced scoring remains future work).
- [x] Add persistent sessions/history and atomic versioned turns (revision `20261029_0006`, NOT RUN).
- [ ] Complete frontend screens, tests and deployment.
- [x] Add deterministic interview policy, final practice reports and readiness contract (backend MVP implementation; new tests/runtime checks NOT RUN).
# Interview workspace implementation

Responsive `/interview` setup/chat/report UI, same-origin API proxy, per-tab recovery
and idempotent retries implemented. No dependencies added. Tests/build/runtime NOT RUN.
Owner commands and changed files: [interview workspace](interview-ui.md).

