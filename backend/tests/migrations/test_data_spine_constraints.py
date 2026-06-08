"""Constraint tests for migration 0001_data_spine.

These verify the spec acceptance criteria that round-trip table-presence tests
do not catch: the partial unique index on rules, ON DELETE RESTRICT on FKs,
and CHECK constraints on enum-shaped columns.
"""

import os
import uuid
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..")

# SQL templates used in multiple fixtures/tests.
_INSERT_JURIS = (
    "INSERT INTO jurisdictions"
    " (id, name, slug, type, country, supported_status)"
    " VALUES (:id, 'Test City', :slug, 'city', 'US', 'supported')"
)
_INSERT_MATERIAL = (
    "INSERT INTO materials"
    " (id, canonical_name, slug, category)"
    " VALUES (:id, 'Test Material', :slug, 'metal')"
)
_INSERT_SOURCE_DOC = (
    "INSERT INTO source_documents"
    " (id, jurisdiction_id, url, title,"
    " authority_level, source_text, source_text_hash)"
    " VALUES (:id, :juris, 'http://example.test',"
    " 'Test', 1, 'text', 'hash')"
)
_INSERT_RULE = (
    "INSERT INTO rules"
    " (id, jurisdiction_id, material_id,"
    " disposition, accepted_status,"
    " source_document_id, source_quote, superseded_by)"
    " VALUES (:id, :j, :m,"
    " 'curbside_recycle', 'accepted', :s, 'quote', :sb)"
)
_INSERT_RULE_ACTIVE = (
    "INSERT INTO rules"
    " (id, jurisdiction_id, material_id, disposition,"
    " accepted_status, source_document_id, source_quote)"
    " VALUES (:id, :j, :m, 'curbside_recycle', 'accepted',"
    " :s, 'active')"
)
_INSERT_RULE_HISTORICAL = (
    "INSERT INTO rules"
    " (id, jurisdiction_id, material_id,"
    " disposition, accepted_status,"
    " source_document_id, source_quote, superseded_by)"
    " VALUES (:id, :j, :m, 'curbside_recycle', 'accepted',"
    " :s, 'historical', :sb)"
)
_INSERT_JURIS_BAD_TYPE = (
    "INSERT INTO jurisdictions"
    " (id, name, slug, type, country, supported_status)"
    " VALUES (:id, 'X', :slug, 'planet', 'US', 'supported')"
)
_INSERT_MATERIAL_BAD_CAT = (
    "INSERT INTO materials"
    " (id, canonical_name, slug, category)"
    " VALUES (:id, 'X', :slug, 'antimatter')"
)
_INSERT_RULE_BAD_DISP = (
    "INSERT INTO rules"
    " (id, jurisdiction_id, material_id, disposition,"
    " accepted_status, source_document_id, source_quote)"
    " VALUES (:id, :j, :m, 'incinerate', 'accepted', :s, 'q')"
)


@pytest.fixture(scope="module")
def alembic_cfg(db_url: str) -> Config:
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option(
        "script_location", os.path.join(BACKEND_DIR, "migrations")
    )
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture(scope="module")
def engine(db_url: str, alembic_cfg: Config) -> Generator[Engine]:
    # lock_timeout so blocked DDL fails fast instead of hanging the suite.
    eng = create_engine(
        db_url, connect_args={"options": "-c lock_timeout=5000"}
    )
    command.upgrade(alembic_cfg, "head")
    yield eng
    # Ensure the test DB is at head on teardown (it should already be, but
    # be explicit so non-migration tests that follow are unaffected).
    command.upgrade(alembic_cfg, "head")
    eng.dispose()


@pytest.fixture
def fixture_ids(
    engine: Engine,
) -> Generator[tuple[uuid.UUID, uuid.UUID, uuid.UUID]]:
    """Insert a jurisdiction, material, source_document; clean up after."""
    juris_id = uuid.uuid4()
    material_id = uuid.uuid4()
    source_doc_id = uuid.uuid4()
    with engine.begin() as conn:
        _ = conn.execute(
            text(_INSERT_JURIS),
            {"id": juris_id, "slug": f"test-{juris_id.hex[:8]}"},
        )
        _ = conn.execute(
            text(_INSERT_MATERIAL),
            {"id": material_id, "slug": f"mat-{material_id.hex[:8]}"},
        )
        _ = conn.execute(
            text(_INSERT_SOURCE_DOC),
            {"id": source_doc_id, "juris": juris_id},
        )
    yield juris_id, material_id, source_doc_id
    with engine.begin() as conn:
        _ = conn.execute(
            text("DELETE FROM rules WHERE jurisdiction_id = :j"),
            {"j": juris_id},
        )
        _ = conn.execute(
            text("DELETE FROM source_documents WHERE id = :id"),
            {"id": source_doc_id},
        )
        _ = conn.execute(
            text("DELETE FROM materials WHERE id = :id"),
            {"id": material_id},
        )
        _ = conn.execute(
            text("DELETE FROM jurisdictions WHERE id = :id"),
            {"id": juris_id},
        )


def _insert_rule(
    conn: Connection,
    juris_id: uuid.UUID,
    material_id: uuid.UUID,
    source_doc_id: uuid.UUID,
    superseded_by: uuid.UUID | None = None,
) -> None:
    _ = conn.execute(
        text(_INSERT_RULE),
        {
            "id": uuid.uuid4(),
            "j": juris_id,
            "m": material_id,
            "s": source_doc_id,
            "sb": superseded_by,
        },
    )


@pytest.mark.integration
def test_rules_partial_unique_blocks_two_active(
    engine: Engine,
    fixture_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    """Two active rules for the same (jurisdiction, material) must conflict."""
    juris_id, material_id, source_doc_id = fixture_ids
    with engine.begin() as conn:
        _insert_rule(conn, juris_id, material_id, source_doc_id)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _insert_rule(conn, juris_id, material_id, source_doc_id)


@pytest.mark.integration
def test_rules_partial_unique_allows_superseded(
    engine: Engine,
    fixture_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    """A second rule is allowed when superseded_by is NOT NULL.

    The partial index only restricts active (NULL superseded_by) rows.
    """
    juris_id, material_id, source_doc_id = fixture_ids
    active_id = uuid.uuid4()
    historical_id = uuid.uuid4()
    with engine.begin() as conn:
        _ = conn.execute(
            text(_INSERT_RULE_ACTIVE),
            {
                "id": active_id,
                "j": juris_id,
                "m": material_id,
                "s": source_doc_id,
            },
        )
        _ = conn.execute(
            text(_INSERT_RULE_HISTORICAL),
            {
                "id": historical_id,
                "j": juris_id,
                "m": material_id,
                "s": source_doc_id,
                "sb": active_id,
            },
        )


@pytest.mark.integration
def test_jurisdiction_delete_restricted_by_source_document(
    engine: Engine,
    fixture_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    """Deleting a jurisdiction with a source_document must raise (RESTRICT)."""
    juris_id, _mat, _src = fixture_ids
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _ = conn.execute(
            text("DELETE FROM jurisdictions WHERE id = :id"),
            {"id": juris_id},
        )


@pytest.mark.integration
def test_material_delete_restricted_by_rule(
    engine: Engine,
    fixture_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    """Deleting a material referenced by a rule must raise (RESTRICT)."""
    juris_id, material_id, source_doc_id = fixture_ids
    with engine.begin() as conn:
        _insert_rule(conn, juris_id, material_id, source_doc_id)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _ = conn.execute(
            text("DELETE FROM materials WHERE id = :id"),
            {"id": material_id},
        )


@pytest.mark.integration
def test_check_constraint_jurisdiction_type(engine: Engine) -> None:
    """Out-of-enum jurisdiction.type must violate ck_jurisdictions_type."""
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _ = conn.execute(
            text(_INSERT_JURIS_BAD_TYPE),
            {"id": uuid.uuid4(), "slug": f"bad-{uuid.uuid4().hex[:8]}"},
        )


@pytest.mark.integration
def test_check_constraint_material_category(engine: Engine) -> None:
    """Out-of-enum material.category must violate ck_materials_category."""
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _ = conn.execute(
            text(_INSERT_MATERIAL_BAD_CAT),
            {"id": uuid.uuid4(), "slug": f"bad-{uuid.uuid4().hex[:8]}"},
        )


@pytest.mark.integration
def test_check_constraint_rule_disposition(
    engine: Engine,
    fixture_ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    """Out-of-enum rule.disposition must violate ck_rules_disposition."""
    juris_id, material_id, source_doc_id = fixture_ids
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _ = conn.execute(
            text(_INSERT_RULE_BAD_DISP),
            {
                "id": uuid.uuid4(),
                "j": juris_id,
                "m": material_id,
                "s": source_doc_id,
            },
        )
