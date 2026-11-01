"""Readiness queries only; never create or alter schema."""
from sqlalchemy import select, text

from app.db.database import SessionLocal
from app.db.models import CodeChunk, InterviewSession, InterviewTurn


def database_ready():
    with SessionLocal() as session, session.begin():
        session.execute(text("SET LOCAL statement_timeout = '3s'"))
        for model in (CodeChunk, InterviewSession, InterviewTurn):
            session.execute(select(model).limit(0))
