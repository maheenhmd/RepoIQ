# RepoIQ

FastAPI + Next.js application for repository-aware technical interviews.

Public GitHub metadata, file discovery/filtering and bounded ingestion preview are implemented. PostgreSQL models and the initial Alembic migration are present, but persistence is not wired into ingestion yet.

## Backend (PowerShell)

```powershell
cd backend
Copy-Item .env.example .env
# Add the Neon pooled DATABASE_URL and direct DIRECT_DATABASE_URL to .env.
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for the API.

## Frontend (PowerShell)

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

## Planned workflow

GitHub URL -> import & filter files -> index & retrieve code -> generate questions -> evaluate answers -> persist history.

See `docs/architecture.md` and `docs/milestones.md`.
