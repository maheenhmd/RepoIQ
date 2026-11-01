from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.integrations.llm_client import LLMError
from app.schemas.interview import StartInterview, CandidateAnswer, InterviewResponse, InterviewHistory, InterviewReport
from app.services import question_generator as interviews
from app.services.code_search import SearchError

router = APIRouter()


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
