"""DB-backed integration tests for PgAnswerAuditRecordRepo.

These tests require a live Postgres connection; they are skipped when the
database is unreachable (via the db_session fixture).

Each test runs inside a transaction that is rolled back on teardown,
leaving the DB clean for the next test.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, text
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
from src.domain.retrieval.evaluated_answer import NoEvaluationReason
from src.domain.retrieval.item_verdict import Accepted, NotCovered, citations_of
from src.infra.db.repos.answer_audit_record_repo import PgAnswerAuditRecordRepo

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
        verdict=Accepted(
            citations=(
                Citation(
                    title="Denver Recycling Guide",
                    url=source_url,
                    quote="Cardboard is accepted.",
                ),
            )
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
    # Citation roundtrip -- citations live on the verdict after refactor.
    loaded_cits = citations_of(loaded.verdict)
    record_cits = citations_of(record.verdict)
    assert len(loaded_cits) == 1
    assert loaded_cits[0].url == record_cits[0].url
    assert loaded_cits[0].title == record_cits[0].title
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
    record = AnswerAuditRecord(
        id=AnswerAuditRecordId(uuid.uuid4()),
        query_text="Can I recycle glass in Aurora?",
        query_location_input="Aurora",
        jurisdiction_id=ooj,
        verdict=NotCovered(),
        retrieved_source_urls=frozenset(),
        recommended_action="Aurora is not covered yet.",
        prompt_version="no_evaluation",
        model_id="none",
        latency_ms=0,
        created_at=datetime.now(UTC),
        no_evaluation_reason=NoEvaluationReason.OUT_OF_JURISDICTION,
    )
    repo = PgAnswerAuditRecordRepo(db_session)

    # Must not raise: previously wrote the sentinel into the FK column,
    # producing an IntegrityError mistranslated as DuplicateAggregateError.
    repo.save(record)

    loaded = repo.find_by_id(record.id)
    assert loaded is not None
    assert loaded.jurisdiction_id == ooj


@pytest.mark.parametrize(
    "reason",
    [
        NoEvaluationReason.LLM_REJECTED,
        NoEvaluationReason.UNCERTAIN_MATERIAL,
        NoEvaluationReason.AMBIGUOUS_MATERIAL,
    ],
)
def test_no_evaluation_reason_enum_label_persists(
    db_session: Session, reason: NoEvaluationReason
) -> None:
    """The reasons added by migration 0003 are accepted by the Postgres enum.

    The rename was folded into 0003 (ambiguous_material), so a typo in its
    ALTER TYPE ... ADD VALUE would surface only on write. Save a record with
    each label and read it back from the actual enum column to prove the type
    accepts it -- the ORM/StrEnum declarations alone do not.
    """
    record = AnswerAuditRecord(
        id=AnswerAuditRecordId(uuid.uuid4()),
        query_text="Is cardboard recyclable?",
        query_location_input="Denver, CO",
        jurisdiction_id=JurisdictionId(uuid.UUID(int=0)),
        verdict=NotCovered(),
        retrieved_source_urls=frozenset(),
        recommended_action="No conclusive rule.",
        prompt_version="no_evaluation",
        model_id="none",
        latency_ms=0,
        created_at=datetime.now(UTC),
        no_evaluation_reason=reason,
    )
    repo = PgAnswerAuditRecordRepo(db_session)
    repo.save(record)

    stored = db_session.execute(
        text(
            "SELECT no_evaluation_reason FROM answer_audit_records WHERE id = :id"  # noqa: E501
        ),
        {"id": str(record.id.value)},
    ).scalar_one()
    assert stored == reason.value


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
        verdict=Accepted(
            citations=(
                Citation(
                    title="Source",
                    url="https://example.gov/recycling",
                    quote=None,
                ),
            )
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
    record = _make_record(jid)

    try:
        with pytest.raises(RepositoryConcurrencyError):
            repo.save(record)
    finally:
        broken_session.close()
        conn.close()
