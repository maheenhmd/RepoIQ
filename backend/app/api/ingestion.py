"""Queue and observe ingestion; HTTP polling never processes work."""

from collections.abc import Generator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import ingestion as storage
from app.schemas.ingestion import IngestionErrorResponse, IngestionJobResponse, StartIngestionRequest
from app.services.ingestion import status_payload


router = APIRouter()


def ingestion_session() -> Generator[Session, None, None]:
    try:
        with storage.request_session() as session:
            yield session
    except storage.JobAccessError as exc:
        raise HTTPException(exc.status_code, str(exc)) from None
    except SQLAlchemyError as exc:
        if getattr(getattr(exc, "orig", None), "sqlstate", None) == "55P03":
            raise HTTPException(409, "Job is busy; retry after the active batch", headers={"Retry-After": "2"}) from None
        raise HTTPException(503, "Ingestion database unavailable", headers={"Retry-After": "5"}) from None


@router.post("", response_model=IngestionJobResponse, status_code=202)
def start_ingestion(payload: StartIngestionRequest, session: Session = Depends(ingestion_session)):
    job = storage.enqueue(session, payload.url, payload.request_id, payload.ref,
                          payload.batch_size or get_settings().ingestion_batch_size)
    return status_payload(job)


@router.get("/{job_id}", response_model=IngestionJobResponse)
def get_status(job_id: UUID, session: Session = Depends(ingestion_session)):
    return status_payload(storage.get_job(session, job_id))


@router.get("/{job_id}/errors", response_model=list[IngestionErrorResponse])
def get_errors(job_id: UUID, offset: int = Query(default=0, ge=0, le=100000),
               limit: int = Query(default=20, ge=1, le=100),
               session: Session = Depends(ingestion_session)):
    return storage.list_errors(session, job_id, offset, limit)


@router.post("/{job_id}/cancel", response_model=IngestionJobResponse)
def cancel_ingestion(job_id: UUID, session: Session = Depends(ingestion_session)):
    job = storage.cancel(session, job_id)
    return status_payload(job)
