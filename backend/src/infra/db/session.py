"""SQLAlchemy session factory.

The engine is created lazily on first use so that importing this module
does not fail when DATABASE_URL is unset. The boot check in src/main.py
catches the missing env var before any request is served.
"""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _get_engine() -> Engine:
    """Return the engine, creating it on first call."""
    global _engine  # noqa: PLW0603
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def _get_session_factory() -> sessionmaker[Session]:
    """Return the session factory, creating it on first call."""
    global _SessionLocal  # noqa: PLW0603
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=_get_engine(), autoflush=False, autocommit=False
        )
    return _SessionLocal


def get_session() -> Generator[Session]:
    """Yield a database session, rolling back on exception."""
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_engine() -> Engine:
    return _get_engine()
