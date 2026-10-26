from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    # Keep existing preview/health routes usable without database configuration.
    settings = get_settings()
    engine = create_engine(
        settings.sqlalchemy_database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_timeout=5,
        connect_args={"connect_timeout": 5},
        echo=False,
        hide_parameters=True,
    )
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def SessionLocal() -> Session:
    return get_session_factory()()


def get_db_session() -> Generator[Session, None, None]:
    """Provide one SQLAlchemy session for a request or service operation."""

    with SessionLocal() as session:
        yield session
