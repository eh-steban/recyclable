"""DB-backed integration tests for PgAnswerAuditRecordRepo.

These tests require a live Postgres connection; they are skipped when the
database is unreachable (via the db_url fixture).

Each test runs inside a transaction that is rolled back on teardown,
leaving the DB clean for the next test.
"""

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError as SQLAOperationalError
from sqlalchemy.orm import Session

from src.domain.audit.answer_audit_record import (
    AnswerAuditRecord,
    AnswerAuditRecordId,
)
from src.domain.exceptions import (
    DuplicateAggregateError,
    RepositoryConcurrencyError,
)
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.retrieval.citation import Citation
from src.domain.retrieval.item_verdict import Accepted
from src.infra.db.repos.answer_audit_record_repo import PgAnswerAuditRecordRepo

# ---------------------------------------------------------------------------
# Session fixture: rolls back after each test (SAVEPOINT pattern)
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine_for_audit(db_url: str) -> Generator[Engine]:
    engine = create_engine(db_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine_for_audit: Engine) -> Generator[Session]:
    """Yield a Session wrapped in a transaction that rolls back on teardown."""
    conn = db_engine_for_audit.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    # Ensure audit table exists (skip test if not).
    try:
        _ = conn.execute(text("SELECT 1 FROM answer_audit_records LIMIT 0"))
    except Exception:
        session.close()
        trans.rollback()
        conn.close()
        pytest.skip("answer_audit_records table not found -- migration needed")
    yield session
    session.close()
    trans.rollback()
    conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_jurisdiction(session: Session) -> JurisdictionId:
    """Insert a minimal jurisdiction row and return its typed id."""
    jid = uuid.uuid4()
    _ = session.execute(
        text(
            "INSERT INTO jurisdictions (id, name, slug, type, country, supported_status) VALUES (:id, :name, :slug, :type, :country, :status)"  # noqa: E501
        ),
        {
            "id": str(jid),
            "name": "Test City",
            "slug": f"test-city-{jid}",
            "type": "city",
            "country": "US",
            "status": "supported",
        },
    )
    return JurisdictionId(jid)


def _make_record(jurisdiction_id: JurisdictionId) -> AnswerAuditRecord:
    """Build a valid AnswerAuditRecord with one citation."""
    source_url = "https://example.gov/recycling"
    return AnswerAuditRecord(
        id=AnswerAuditRecordId(uuid.uuid4()),
        query_text="Is cardboard recyclable?",
        query_location_input="Denver, CO",
        jurisdiction_id=jurisdiction_id,
        verdict=Accepted(),
        citations=(
            Citation(
                title="Denver Recycling Guide",
                url=source_url,
                quote="Cardboard is accepted.",
            ),
        ),
        retrieved_source_urls=frozenset({source_url}),
        recommended_action="Place flattened in the blue bin.",
        prompt_version="ask_compose_v1",
        model_id="claude-sonnet-4-6",
        latency_ms=1234,
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_save_and_find_roundtrip(db_session: Session) -> None:
    """save() then find_by_id() returns an equivalent AnswerAuditRecord."""
    jid = _make_jurisdiction(db_session)
    record = _make_record(jid)
    repo = PgAnswerAuditRecordRepo(db_session)
    repo.save(record)

    loaded = repo.find_by_id(record.id)

    assert loaded is not None
    assert loaded.id == record.id
    assert loaded.query_text == record.query_text
    assert loaded.jurisdiction_id == record.jurisdiction_id
    assert loaded.recommended_action == record.recommended_action
    assert loaded.prompt_version == record.prompt_version
    assert loaded.model_id == record.model_id
    # Pin the verdict-type roundtrip so a stub _wire_to_verdict returning
    # NotCovered would not silently pass.
    assert isinstance(loaded.verdict, Accepted)
    # Citation roundtrip.
    assert len(loaded.citations) == 1
    assert loaded.citations[0].url == record.citations[0].url
    assert loaded.citations[0].title == record.citations[0].title
    # retrieved_source_urls roundtrip via validator_findings JSONB.
    assert loaded.retrieved_source_urls == record.retrieved_source_urls


def test_find_by_id_returns_none_for_unknown(db_session: Session) -> None:
    """find_by_id() returns None for an id that was never saved."""
    repo = PgAnswerAuditRecordRepo(db_session)
    result = repo.find_by_id(AnswerAuditRecordId(uuid.uuid4()))
    assert result is None


def test_duplicate_id_raises_duplicate_aggregate_error(
    db_session: Session,
) -> None:
    """Inserting two rows with the same id raises DuplicateAggregateError.

    The application layer must never import sqlalchemy.exc.IntegrityError.
    """
    jid = _make_jurisdiction(db_session)
    record = _make_record(jid)
    repo = PgAnswerAuditRecordRepo(db_session)
    repo.save(record)
    db_session.flush()  # flush to materialise the first insert

    # Attempt to insert a second row with the same PK.
    duplicate = AnswerAuditRecord(
        id=record.id,  # same id -- PK violation
        query_text="Different query",
        query_location_input="Denver, CO",
        jurisdiction_id=jid,
        verdict=Accepted(),
        citations=(
            Citation(
                title="Source",
                url="https://example.gov/recycling",
                quote=None,
            ),
        ),
        retrieved_source_urls=frozenset({"https://example.gov/recycling"}),
        recommended_action="action",
        prompt_version="ask_compose_v1",
        model_id="claude-sonnet-4-6",
        latency_ms=100,
        created_at=datetime.now(UTC),
    )
    with pytest.raises(DuplicateAggregateError):
        repo.save(duplicate)


def test_closed_session_raises_repository_concurrency_error() -> None:
    """Passing a closed session raises RepositoryConcurrencyError, not
    sqlalchemy.exc.OperationalError.
    """
    db_url_env = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://recyclable:recyclable_dev@localhost:5432/recyclable",
    )
    try:
        engine = create_engine(db_url_env, pool_pre_ping=True)
        with engine.connect():
            pass
    except SQLAOperationalError:
        pytest.skip("Postgres unreachable")

    # Create and immediately close a session.
    closed_session = Session(engine)
    closed_session.close()

    repo = PgAnswerAuditRecordRepo(closed_session)
    jid = JurisdictionId(uuid.uuid4())
    record = _make_record(jid)

    with pytest.raises(RepositoryConcurrencyError):
        repo.save(record)
        closed_session.flush()
