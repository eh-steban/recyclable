"""Shared test fixtures.

Integration tests that need a real Postgres connection consume the `db_url`
fixture, which probes connectivity and skips the test (rather than failing)
when the database is unreachable.

In-memory fake-repo fixtures are exposed here for application and domain
tests that should never touch the database.
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from tests._fakes.answer_audit_record_repo import MemAnswerAuditRecordRepo
from tests._fakes.jurisdiction_repo import MemJurisdictionRepo
from tests._fakes.material_repo import MemMaterialRepo
from tests._fakes.rule_repo import MemRuleRepo
from tests._fakes.source_repo import MemSourceRepo

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://recyclable:recyclable_dev@localhost:5432/recyclable",
)


@pytest.fixture(scope="session")
def db_url() -> str:
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect():
            pass
        engine.dispose()
    except OperationalError as exc:
        pytest.skip(
            f"Postgres unreachable at {DATABASE_URL}: {exc}",
            allow_module_level=True,
        )
    return DATABASE_URL


# ---------------------------------------------------------------------------
# In-memory fake-repo fixtures (function-scoped -- fresh per test)
# ---------------------------------------------------------------------------


@pytest.fixture()
def mem_jurisdiction_repo() -> MemJurisdictionRepo:
    """Return a fresh MemJurisdictionRepo instance."""
    return MemJurisdictionRepo()


@pytest.fixture()
def mem_material_repo() -> MemMaterialRepo:
    """Return a fresh MemMaterialRepo instance."""
    return MemMaterialRepo()


@pytest.fixture()
def mem_rule_repo() -> MemRuleRepo:
    """Return a fresh MemRuleRepo instance."""
    return MemRuleRepo()


@pytest.fixture()
def mem_source_repo() -> MemSourceRepo:
    """Return a fresh MemSourceRepo instance."""
    return MemSourceRepo()


@pytest.fixture()
def mem_answer_audit_record_repo() -> MemAnswerAuditRecordRepo:
    """Return a fresh MemAnswerAuditRecordRepo instance."""
    return MemAnswerAuditRecordRepo()
