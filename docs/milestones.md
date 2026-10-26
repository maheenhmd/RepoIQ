# RepoIQ milestone checklist

- [ ] Add GitHub URL validation and metadata import.
- [ ] Filter files and enforce size/security constraints.
- [x] Add the PostgreSQL/Neon ORM foundation and initial Alembic migration (applied to Neon, owner reported).
- [x] Make full source storage optional with revision `20261026_0002` (migration and tests not run).
- [x] Implement automatic, commit-pinned ingestion with a PostgreSQL queue, bounded worker batches, persisted retries, status/errors/cancel APIs and revision `20261026_0003` (not executed or tested).
- [ ] Index the code and implement repository-aware retrieval.
- [x] Implement standalone deterministic Python AST chunking with bounded text fallback (Phase 3.1; tests/runtime verification not run).
- [x] Add hybrid Tree-sitter chunking for JavaScript/JSX, TypeScript/TSX, Java and C# while preserving Python AST behavior (Phase 3.2; tests/runtime verification not run).
- [ ] Generate interview questions from relevant code.
- [ ] Evaluate user answers against code context.
- [ ] Save interview sessions and history to a database.
- [ ] Complete frontend screens, tests and deployment.
