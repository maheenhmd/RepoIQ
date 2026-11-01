from uuid import UUID

from fastapi import APIRouter, HTTPException, Body

from app.integrations.llm_client import LLMError
from app.schemas.interview import StartInterview, CandidateAnswer, InterviewResponse, InterviewHistory, InterviewReport
from app.services import question_generator as interviews
from app.services.code_search import SearchError

router = APIRouter()


@router.post('/lookup')
def lookup_interviews(repository_id: UUID = Body(embed=True)):
    from sqlalchemy import select
    from sqlalchemy.exc import SQLAlchemyError
    from app.db.ingestion import request_session
    from app.db.models import InterviewSession
    try:
        with request_session() as session:
            rows = session.execute(select(InterviewSession.id, InterviewSession.status,
                InterviewSession.updated_at, InterviewSession.initial_request).where(
                InterviewSession.repository_id == repository_id).order_by(
                InterviewSession.updated_at.desc(), InterviewSession.id).limit(20)).all()
            return [{'session_id': row.id, 'status': row.status,
                     'updated_at': row.updated_at, 'topic': row.initial_request.get('topic', '')} for row in rows]
    except SQLAlchemyError:
        raise HTTPException(503, 'Interview history unavailable') from None


def _call(operation, *args):
    try:
        return operation(*args)
    except (SearchError, LLMError) as exc:
        headers = {'Retry-After': '5'} if exc.status_code in {429, 503, 504} else None
        raise HTTPException(status_code=exc.status_code, detail=str(exc), headers=headers) from None


@router.post('/start', response_model=InterviewResponse)
def start_interview(payload: StartInterview):
    return _call(interviews.start_interview, payload)


@router.post('/{session_id}/answers', response_model=InterviewResponse)
def answer_interview(session_id: UUID, payload: CandidateAnswer):
    return _call(interviews.answer_interview, session_id, payload)


@router.get('/{session_id}', response_model=InterviewHistory)
def get_interview(session_id: UUID):
    return _call(interviews.get_interview, session_id)


@router.get('/{session_id}/report', response_model=InterviewReport,
            responses={404: {'description': 'Session not found'}, 409: {'description': 'Interview incomplete'}})
def get_report(session_id: UUID):
    """Retrieve the persisted final practice report; no model inference."""
    return _call(interviews.get_report, session_id)
