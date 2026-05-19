"""Shared fixtures for CLI integration tests.

All tests in this package require a live Postgres connection.  If the
database is unreachable the tests are skipped (not failed) via the
``db_engine`` fixture from the root conftest.

Each test that needs a clean slate calls the ``clean_db`` fixture, which
truncates the relevant tables inside a savepoint-protected block.  This
avoids the cost of a full migration round-trip per test.
"""

from collections.abc import Generator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

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
