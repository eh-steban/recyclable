"""DB-backed integration tests for PgRuleRepo.find_for().

Verifies:
- Active rule is returned; superseded rule is not.
- Exact-tuple match: unseeded material -> []; seeded material in second
  jurisdiction (no rule) -> [].
- Partial unique index enforces at-most-one active rule per tuple.
"""

import hashlib
import uuid
from collections.abc import Generator
from datetime import date

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.material import MaterialId
from src.infra.db.repos.rule_repo import PgRuleRepo

# ---------------------------------------------------------------------------
# Session fixture (rolls back after each test)
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine_rules(db_url: str) -> Generator[Engine]:
    engine = create_engine(db_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine_rules: Engine) -> Generator[Session]:
    conn = db_engine_rules.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    try:
        _ = conn.execute(text("SELECT 1 FROM rules LIMIT 0"))
    except Exception:
        session.close()
        trans.rollback()
        conn.close()
        pytest.skip("rules table not found -- migration needed")
    yield session
    session.close()
    trans.rollback()
    conn.close()


# ---------------------------------------------------------------------------
# Seed helpers (raw SQL to avoid depending on repo save())
# ---------------------------------------------------------------------------


def _insert_jurisdiction(session: Session, slug: str) -> uuid.UUID:
    jid = uuid.uuid4()
    _ = session.execute(
        text(
            "INSERT INTO jurisdictions (id, name, slug, type, country, supported_status) VALUES (:id, :name, :slug, :type, :country, :status)"  # noqa: E501
        ),
        {
            "id": str(jid),
            "name": f"Jurisdiction {slug}",
            "slug": slug,
            "type": "city",
            "country": "US",
            "status": "supported",
        },
    )
    return jid


def _insert_material(session: Session, slug: str) -> uuid.UUID:
    mid = uuid.uuid4()
    _ = session.execute(
        text(
            "INSERT INTO materials (id, canonical_name, slug, category) VALUES (:id, :name, :slug, :category)"  # noqa: E501
        ),
        {"id": str(mid), "name": slug, "slug": slug, "category": "paper"},
    )
    return mid


def _insert_source(session: Session, jid: uuid.UUID) -> uuid.UUID:
    sid = uuid.uuid4()
    url = f"https://example.gov/{sid}"
    body = "Source text for testing."
    _ = session.execute(
        text(
            "INSERT INTO source_documents (id, jurisdiction_id, url, title, authority_level, fetched_at, source_text, source_text_hash) VALUES (:id, :jid, :url, :title, :auth, now(), :txt, :hash)"  # noqa: E501
        ),
        {
            "id": str(sid),
            "jid": str(jid),
            "url": url,
            "title": "Test Source",
            "auth": 1,
            "txt": body,
            "hash": hashlib.sha256(body.encode()).hexdigest(),
        },
    )
    return sid


def _insert_rule(
    session: Session,
    jid: uuid.UUID,
    mid: uuid.UUID,
    sid: uuid.UUID,
    *,
    superseded_by: uuid.UUID | None = None,
    effective_from: date | None = None,
) -> uuid.UUID:
    rid = uuid.uuid4()
    _ = session.execute(
        text(
            "INSERT INTO rules (id, jurisdiction_id, material_id, disposition, accepted_status, source_document_id, source_quote, confidence, effective_from, superseded_by) VALUES (:id, :jid, :mid, :disp, :status, :sid, :quote, :conf, :eff, :sup)"  # noqa: E501
        ),
        {
            "id": str(rid),
            "jid": str(jid),
            "mid": str(mid),
            "disp": "curbside_recycle",
            "status": "accepted",
            "sid": str(sid),
            "quote": "Cardboard is accepted.",
            "conf": "high",
            "eff": effective_from,
            "sup": str(superseded_by) if superseded_by else None,
        },
    )
    return rid


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_find_for_returns_active_rule(db_session: Session) -> None:
    """find_for() returns the active rule and ignores superseded rules."""
    jid = _insert_jurisdiction(db_session, f"denver-{uuid.uuid4()}")
    mid = _insert_material(db_session, f"cardboard-{uuid.uuid4()}")
    sid = _insert_source(db_session, jid)

    # Insert active rule.
    active_rid = _insert_rule(db_session, jid, mid, sid)
    # Insert superseded rule (points to active_rid as replacement).
    # superseded_by IS NOT NULL, so the partial unique index does not apply.
    _insert_rule(db_session, jid, mid, sid, superseded_by=active_rid)

    repo = PgRuleRepo(db_session)
    results = repo.find_for(JurisdictionId(jid), MaterialId(mid))

    assert len(results) == 1
    assert results[0].id.value == active_rid
    assert results[0].superseded_by is None


def test_find_for_unknown_material_returns_empty(
    db_session: Session,
) -> None:
    """find_for() with a material that has no rule returns []."""
    jid = _insert_jurisdiction(db_session, f"denver-{uuid.uuid4()}")
    unseeded_mid = uuid.uuid4()  # not in DB at all

    repo = PgRuleRepo(db_session)
    results = repo.find_for(JurisdictionId(jid), MaterialId(unseeded_mid))

    assert results == []


def test_find_for_material_in_other_jurisdiction_returns_empty(
    db_session: Session,
) -> None:
    """find_for() returns [] when rule exists only for a different jurisdiction.

    Enforces INV-PROD-002: no cross-jurisdiction fallback.
    """
    # Seed a rule for jurisdiction A + material.
    jid_a = _insert_jurisdiction(db_session, f"city-a-{uuid.uuid4()}")
    mid = _insert_material(db_session, f"cardboard-{uuid.uuid4()}")
    sid_a = _insert_source(db_session, jid_a)
    _insert_rule(db_session, jid_a, mid, sid_a)

    # Query for the same material under jurisdiction B (no rule exists).
    jid_b = _insert_jurisdiction(db_session, f"city-b-{uuid.uuid4()}")

    repo = PgRuleRepo(db_session)
    results = repo.find_for(JurisdictionId(jid_b), MaterialId(mid))

    assert results == []


def test_partial_unique_index_rejects_two_active_rules(
    db_session: Session,
) -> None:
    """The partial unique index enforces at-most-one active rule per tuple.

    Inserting a second active rule for the same (jurisdiction, material) must
    raise an IntegrityError -- demonstrating the index is the enforcement
    mechanism for INV-DATA-002.
    """
    jid = _insert_jurisdiction(db_session, f"denver-{uuid.uuid4()}")
    mid = _insert_material(db_session, f"cardboard-{uuid.uuid4()}")
    sid = _insert_source(db_session, jid)

    _insert_rule(db_session, jid, mid, sid)

    with pytest.raises(IntegrityError):
        _insert_rule(db_session, jid, mid, sid)
        db_session.flush()
