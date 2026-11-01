"""Atomic, resumable NULL-embedding batches, serialized by row locks."""

from contextlib import contextmanager

from sqlalchemy import select, text
from sqlalchemy.orm import load_only

from app.db.database import SessionLocal
from app.db.models import CodeChunk


def validate_dimension(dimension: int) -> None:
    """Fail before inference when runtime and installed schema disagree."""
    with SessionLocal() as session:
        actual = session.scalar(text("""SELECT format_type(atttypid, atttypmod)
            FROM pg_attribute WHERE attrelid = 'code_chunks'::regclass
            AND attname = 'embedding' AND NOT attisdropped"""))
    if actual != f"vector({dimension})":
        raise ValueError("Database embedding dimension does not match configuration; apply migration")


@contextmanager
def claim_batch(size: int):
    with SessionLocal() as session, session.begin():
        session.execute(text("SET LOCAL statement_timeout = '30s'"))
        session.execute(text("SET LOCAL lock_timeout = '2s'"))
        session.execute(text("SET LOCAL idle_in_transaction_session_timeout = '15min'"))
        chunks = list(session.scalars(select(CodeChunk).where(CodeChunk.embedding.is_(None))
            .options(load_only(CodeChunk.id, CodeChunk.content, CodeChunk.context))
            .order_by(CodeChunk.created_at, CodeChunk.id)
            .with_for_update(skip_locked=True).limit(size)))
        yield chunks
        session.flush()


def save_vectors(chunks, vectors, model: str) -> None:
    if len(chunks) != len(vectors):
        raise ValueError("Embedding result count mismatch")
    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk.embedding = vector
        chunk.embedding_model = model
