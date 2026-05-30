"""Shared test fixtures.

Integration tests that need a real Postgres connection consume the
``db_session`` fixture, which provisions a dedicated ``recyclable_test``
database (never the dev ``recyclable`` DB), runs ``alembic upgrade head``
against it once per session, and rolls back every test's writes so state
never persists across tests.

Connectivity is checked once per session; tests are SKIPPED (not failed)
when the Postgres server is unreachable -- the same behaviour as the old
``db_url`` fixture.

In-memory fake-repo fixtures are exposed here for application and domain
tests that should never touch the database.
"""

import contextlib
import os
import subprocess
import warnings
from collections.abc import Generator
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from tests._fakes.answer_audit_record_repo import MemAnswerAuditRecordRepo
from tests._fakes.jurisdiction_repo import MemJurisdictionRepo
from tests._fakes.material_repo import MemMaterialRepo
from tests._fakes.rule_repo import MemRuleRepo
from tests._fakes.source_repo import MemSourceRepo

# ---------------------------------------------------------------------------
# Test-database URL -- NEVER the dev ``recyclable`` database
# ---------------------------------------------------------------------------

load_dotenv(Path(__file__).parent.parent / ".env.test", override=False)

TEST_DATABASE_URL: str = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://recyclable:recyclable_dev@localhost:5432/recyclable_test",
)

# Derive the maintenance-DB URL by swapping the database name for "postgres".
# This is used to CREATE the test database when it does not yet exist.
_MAINTENANCE_URL: str = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"

# ---------------------------------------------------------------------------
# Session-scoped: provision test DB + run migrations once per test session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def provision_test_db() -> None:
    """Create ``recyclable_test`` if absent, then run ``alembic upgrade head``.

    Uses an AUTOCOMMIT connection to the maintenance database so the
    ``CREATE DATABASE`` statement is not inside a transaction (Postgres
    forbids DDL in multi-statement transactions).  "Already exists" errors
    are silently ignored.

    Skips the whole session (and therefore all tests that depend on this
    fixture) when the Postgres server is unreachable.
    """
    # Probe reachability via the maintenance DB first.
    try:
        maint_engine = create_engine(
            _MAINTENANCE_URL,
            isolation_level="AUTOCOMMIT",
        )
        with maint_engine.connect() as conn, contextlib.suppress(Exception):
            # CREATE DATABASE IF NOT EXISTS is not valid Postgres syntax;
            # ignore the "already exists" error instead.
            conn.execute(text("CREATE DATABASE recyclable_test"))
        maint_engine.dispose()
    except OperationalError as exc:
        pytest.skip(
            f"Postgres unreachable at {_MAINTENANCE_URL}: {exc}",
            allow_module_level=True,
        )

    # Run alembic upgrade head against the test DB.
    backend_dir = os.path.join(os.path.dirname(__file__), "..")
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        out = result.stdout
        err = result.stderr
        pytest.fail(
            f"alembic upgrade head failed:\nstdout: {out}\nstderr: {err}"
        )


@pytest.fixture(scope="session")
def db_engine(provision_test_db: None) -> Generator[Engine]:
    """Session-scoped SQLAlchemy Engine connected to the test database.

    Skips all dependent tests if the test DB is unreachable after
    provisioning.
    """
    try:
        engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
        with engine.connect():
            pass
    except OperationalError as exc:
        pytest.skip(
            f"Test DB unreachable at {TEST_DATABASE_URL}: {exc}",
            allow_module_level=True,
        )
    yield engine
    engine.dispose()


# ---------------------------------------------------------------------------
# ``db_url`` -- backward-compatible fixture for migration tests and any other
# test that needs the URL string directly (e.g. to build an alembic Config).
# Always returns the TEST database URL, never the dev one.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def db_url(provision_test_db: None) -> str:
    """Return the test-database URL string.

    Exists for backward compatibility with migration tests that build their
    own alembic Config or engine from the URL.  Always points at
    ``recyclable_test``, never at ``recyclable``.
    """
    return TEST_DATABASE_URL


# ---------------------------------------------------------------------------
# Per-test isolation: function-scoped Session with automatic rollback
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session(db_engine: Engine) -> Generator[Session]:
    """Yield a Session bound to a connection-level transaction.

    All writes made during a test are invisible to other connections and
    are rolled back on teardown -- no ``DELETE`` cleanup required, and the
    test-only UUID rows never persist to any database.

    This is the single shared fixture that all DB-touching tests must use.
    Tests that need the raw URL (migration tests) use ``db_url`` instead.
    """
    conn = db_engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    yield session
    session.close()
    # Suppress the SAWarning emitted when a test's IntegrityError already
    # caused SQLAlchemy to deassociate the transaction from the connection.
    # The rollback is still attempted so any other in-flight state is cleaned
    # up; we just don't want the noise in the test output.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with contextlib.suppress(Exception):
            trans.rollback()
    conn.close()


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
