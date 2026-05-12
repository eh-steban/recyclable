"""Shared fixtures for CLI integration tests.

All tests in this package require a live Postgres connection.  If the
database is unreachable the tests are skipped (not failed) via the
``db_session`` fixture.

Each test that needs a clean slate calls the ``clean_db`` fixture, which
truncates the relevant tables inside a savepoint-protected block.  This
avoids the cost of a full migration round-trip per test.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://recyclable:recyclable_dev@localhost:5432/recyclable",
)

# Tables listed in FK-safe truncation order (children before parents).
_TRUNCATE_TABLES = [
    "answer_audit_records",
    "regression_cases",
    "rules",
    "material_aliases",
    "source_documents",
    "materials",
    "jurisdictions",
]


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine]:
    """Create a session-scoped engine, skipping if Postgres is unreachable."""
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with engine.connect():
            pass
    except OperationalError as exc:
        pytest.skip(
            f"Postgres unreachable at {DATABASE_URL}: {exc}",
            allow_module_level=True,
        )
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine: Engine) -> Generator[Session]:
    """Yield an open Session for the duration of one test.

    The session is NOT committed by this fixture -- tests that need to
    commit do so explicitly (e.g. the idempotency test).
    """
    with Session(db_engine) as session:
        yield session


@pytest.fixture()
def clean_db(db_engine: Engine) -> Generator[None]:
    """Truncate all seed tables before (and after) each test."""
    with Session(db_engine) as session, session.begin():
        for table in _TRUNCATE_TABLES:
            _ = session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
    yield
    # Post-test cleanup keeps the DB clean for the next test in the suite.
    with Session(db_engine) as session, session.begin():
        for table in _TRUNCATE_TABLES:
            _ = session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
