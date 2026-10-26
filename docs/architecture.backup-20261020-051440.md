# Architecture

- `backend/app/api/`: HTTP endpoints only.
- `backend/app/services/`: Business logic (import, filtering, indexing, retrieval, questions, grading).
- `backend/app/integrations/`: External provider clients (GitHub, LLM).
- `backend/app/core/`: Application configuration.
- `backend/app/schemas/`: Request and response validation.
- `backend/app/db/`: Persistence infrastructure and models.
- `frontend/src/app/`: Next.js routes.
- `frontend/src/components/`: UI components.
- `frontend/src/lib/`: Shared API client.

Initial scaffold is intentionally minimal. Implement features incrementally; add dependencies only when needed.
