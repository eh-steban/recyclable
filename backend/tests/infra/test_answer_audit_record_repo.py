"""DB-backed integration tests for PgAnswerAuditRecordRepo.

These tests require a live Postgres connection; they are skipped when the
database is unreachable (via the db_session fixture).

Each test runs inside a transaction that is rolled back on teardown,
leaving the DB clean for the next test.
"""

import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from src.domain.audit.answer_audit_record import AnswerAuditRecordId
from src.domain.exceptions import (
    DuplicateAggregateError,
    RepositoryConcurrencyError,
)
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.retrieval.evaluated_answer import NoEvaluationReason
from src.domain.retrieval.item_verdict import Accepted, NotCovered
from src.infra.db.repos.answer_audit_record_repo import PgAnswerAuditRecordRepo
from tests.utils.builders import make_answer_audit_record

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_save_and_find_roundtrip(db_session: Session) -> None:
    """save() then find_by_id() returns an equivalent AnswerAuditRecord."""
    jid = _make_jurisdiction(db_session)
    record = make_answer_audit_record(jurisdiction_id=jid)
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


def test_save_out_of_jurisdiction_record_persists_as_null(
    db_session: Session,
) -> None:
    """An OOJ record (all-zero sentinel jurisdiction_id) saves and reloads.

    The sentinel ``uuid.UUID(int=0)`` is not a real jurisdiction row, so
    writing it into the FK column violates
    ``fk_answer_audit_records_jurisdiction_id``. The save path must store
    NULL -- mirroring the load path's NULL -> sentinel convention -- so the
    out-of-jurisdiction user path (Aurora / Boulder) can record an audit
    row. Regression for the OOJ foreign-key failure.
    """
    ooj = JurisdictionId(uuid.UUID(int=0))
    record = make_answer_audit_record(
        jurisdiction_id=ooj,
        query_text="Can I recycle glass in Aurora?",
        query_location_input="Aurora",
        verdict=NotCovered(),
        citations=(),
        retrieved_source_urls=frozenset(),
        recommended_action="Aurora is not covered yet.",
        prompt_version="no_evaluation",
        model_id="none",
        latency_ms=0,
        no_evaluation_reason=NoEvaluationReason.OUT_OF_JURISDICTION,
    )
    repo = PgAnswerAuditRecordRepo(db_session)

    # Must not raise: previously wrote the sentinel into the FK column,
    # producing an IntegrityError mistranslated as DuplicateAggregateError.
    repo.save(record)

    loaded = repo.find_by_id(record.id)
    assert loaded is not None
    assert loaded.jurisdiction_id == ooj


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
    record = make_answer_audit_record(jurisdiction_id=jid)
    repo = PgAnswerAuditRecordRepo(db_session)
    repo.save(record)
    db_session.flush()  # flush to materialise the first insert

    # Attempt to insert a second row with the same PK.
    duplicate = make_answer_audit_record(id=record.id, jurisdiction_id=jid)
    with pytest.raises(DuplicateAggregateError):
        repo.save(duplicate)


def test_closed_session_raises_repository_concurrency_error(
    db_engine: Engine,
) -> None:
    """Repo raises RepositoryConcurrencyError when the connection is broken.

    Simulates a mid-transaction connection loss (OperationalError) by
    forcibly closing the underlying psycopg driver connection while the
    SQLAlchemy Connection object is still open.  The repo must translate
    the resulting OperationalError into a domain-level
    RepositoryConcurrencyError so the application layer never imports
    sqlalchemy.exc.

    Uses the shared test-DB engine to avoid touching the dev database.
    The engine is already reachability-checked by the session-scoped
    ``db_engine`` fixture -- no separate skip guard needed.
    """
    conn = db_engine.connect()
    # Break the underlying psycopg connection to force an OperationalError
    # on the next DB operation, simulating a lost connection.
    # driver_connection is the raw psycopg Connection object (dbapi-level).
    # We access it via getattr to avoid the Optional-member type error; its
    # presence is guaranteed for a freshly-opened psycopg connection.
    driver = getattr(conn.connection, "driver_connection", None)
    assert driver is not None, "expected a live driver_connection"
    driver.close()

    broken_session = Session(bind=conn)
    repo = PgAnswerAuditRecordRepo(broken_session)
    jid = JurisdictionId(uuid.uuid4())
    record = make_answer_audit_record(jurisdiction_id=jid)

    try:
        with pytest.raises(RepositoryConcurrencyError):
            repo.save(record)
    finally:
        broken_session.close()
        conn.close()
