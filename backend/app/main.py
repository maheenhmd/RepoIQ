from fastapi import FastAPI

from app.api.interviews import router as interviews_router
from app.api.ingestion import router as ingestion_router
from app.api.repositories import router as repositories_router

app = FastAPI(title="RepoIQ API")

app.include_router(repositories_router, prefix="/api/repositories", tags=["repositories"])
app.include_router(interviews_router, prefix="/api/interviews", tags=["interviews"])
app.include_router(ingestion_router, prefix="/api/repositories/ingest", tags=["ingestion"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
