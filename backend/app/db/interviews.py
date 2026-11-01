"""Short transactions only: inference never holds a connection or row lock."""
from sqlalchemy import select, update, text
from sqlalchemy.dialects.postgresql import insert

from app.db.database import SessionLocal
from app.db.models import InterviewSession, InterviewTurn


def _limits(session):
    session.execute(text("SET LOCAL statement_timeout = '10s'"))
    session.execute(text("SET LOCAL lock_timeout = '2s'"))


def load(session_id):
    with SessionLocal() as session, session.begin():
        _limits(session)
        record = session.get(InterviewSession, session_id)
        if record is None:
            return None
        # Restrict to the observed version if a concurrent answer commits now.
        turns = session.scalars(select(InterviewTurn).where(
            InterviewTurn.session_id == session_id, InterviewTurn.sequence <= record.version
        ).order_by(InterviewTurn.sequence).limit(21)).all()
        return dict(initial_request=record.initial_request, version=record.version,
                    turns=[dict(request_id=str(turn.request_id), answer=turn.answer,
                                response=turn.response) for turn in turns])


def create(request, response):
    with SessionLocal() as session, session.begin():
        _limits(session)
        inserted = session.scalar(insert(InterviewSession).values(
            id=response.session_id, repository_id=response.repository_id,
            commit_sha=response.commit_sha, status=response.status, version=0,
            max_turns=response.max_turns, initial_request=request.model_dump(mode='json'),
        ).on_conflict_do_nothing(index_elements=['id']).returning(InterviewSession.id))
        if inserted is None:
            return False
        session.add(InterviewTurn(session_id=response.session_id, sequence=0,
                                 request_id=request.request_id, response=response.model_dump(mode='json')))
    return True


def append(request, response):
    with SessionLocal() as session, session.begin():
        _limits(session)
        updated = session.scalar(update(InterviewSession).where(
            InterviewSession.id == response.session_id,
            InterviewSession.version == request.expected_version,
            InterviewSession.status == 'active',
        ).values(version=response.version, status=response.status).returning(InterviewSession.id))
        if updated is None:
            return False
        session.add(InterviewTurn(session_id=response.session_id, sequence=response.version,
                                 request_id=request.request_id, answer=request.answer,
                                 response=response.model_dump(mode='json')))
    return True
