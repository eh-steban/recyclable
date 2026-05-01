"""Constraint tests for migration 0001_data_spine.

These verify the spec acceptance criteria that round-trip table-presence tests
do not catch: the partial unique index on rules, ON DELETE RESTRICT on FKs,
and CHECK constraints on enum-shaped columns.
"""
from __future__ import annotations

import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..")


@pytest.fixture(scope="module")
def alembic_cfg(db_url):
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture(scope="module")
def engine(db_url, alembic_cfg):
    eng = create_engine(db_url)
    command.upgrade(alembic_cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture
def fixture_ids(engine):
    """Insert a jurisdiction, material, source_document; clean up after."""
    juris_id = uuid.uuid4()
    material_id = uuid.uuid4()
    source_doc_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO jurisdictions (id, name, slug, type, country, supported_status) "
                "VALUES (:id, 'Test City', :slug, 'city', 'US', 'supported')"
            ),
            {"id": juris_id, "slug": f"test-{juris_id.hex[:8]}"},
        )
        conn.execute(
            text(
                "INSERT INTO materials (id, canonical_name, slug, category) "
                "VALUES (:id, 'Test Material', :slug, 'metal')"
            ),
            {"id": material_id, "slug": f"mat-{material_id.hex[:8]}"},
        )
        conn.execute(
            text(
                "INSERT INTO source_documents "
                "(id, jurisdiction_id, url, title, authority_level, source_text, source_text_hash) "
                "VALUES (:id, :juris, 'http://example.test', 'Test', 1, 'text', 'hash')"
            ),
            {"id": source_doc_id, "juris": juris_id},
        )
    yield juris_id, material_id, source_doc_id
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM rules WHERE jurisdiction_id = :j"), {"j": juris_id})
        conn.execute(text("DELETE FROM source_documents WHERE id = :id"), {"id": source_doc_id})
        conn.execute(text("DELETE FROM materials WHERE id = :id"), {"id": material_id})
        conn.execute(text("DELETE FROM jurisdictions WHERE id = :id"), {"id": juris_id})


def _insert_rule(conn, juris_id, material_id, source_doc_id, superseded_by=None):
    conn.execute(
        text(
            "INSERT INTO rules "
            "(id, jurisdiction_id, material_id, disposition, accepted_status, "
            " source_document_id, source_quote, superseded_by) "
            "VALUES (:id, :j, :m, 'curbside_recycle', 'accepted', :s, 'quote', :sb)"
        ),
        {
            "id": uuid.uuid4(),
            "j": juris_id,
            "m": material_id,
            "s": source_doc_id,
            "sb": superseded_by,
        },
    )


@pytest.mark.integration
def test_rules_partial_unique_blocks_two_active(engine, fixture_ids):
    """Two rules for the same (jurisdiction, material) with NULL superseded_by must conflict."""
    juris_id, material_id, source_doc_id = fixture_ids
    with engine.begin() as conn:
        _insert_rule(conn, juris_id, material_id, source_doc_id)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        _insert_rule(conn, juris_id, material_id, source_doc_id)


@pytest.mark.integration
def test_rules_partial_unique_allows_superseded(engine, fixture_ids):
    """A second rule for the same (jurisdiction, material) is allowed when its
    superseded_by is NOT NULL -- the partial index only restricts active rows."""
    juris_id, material_id, source_doc_id = fixture_ids
    active_id = uuid.uuid4()
    historical_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO rules "
                "(id, jurisdiction_id, material_id, disposition, accepted_status, "
                " source_document_id, source_quote) "
                "VALUES (:id, :j, :m, 'curbside_recycle', 'accepted', :s, 'active')"
            ),
            {"id": active_id, "j": juris_id, "m": material_id, "s": source_doc_id},
        )
        conn.execute(
            text(
                "INSERT INTO rules "
                "(id, jurisdiction_id, material_id, disposition, accepted_status, "
                " source_document_id, source_quote, superseded_by) "
                "VALUES (:id, :j, :m, 'curbside_recycle', 'accepted', :s, 'historical', :sb)"
            ),
            {
                "id": historical_id,
                "j": juris_id,
                "m": material_id,
                "s": source_doc_id,
                "sb": active_id,
            },
        )


@pytest.mark.integration
def test_jurisdiction_delete_restricted_by_source_document(engine, fixture_ids):
    """Deleting a jurisdiction with a source_document must raise (RESTRICT)."""
    juris_id, _, _ = fixture_ids
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("DELETE FROM jurisdictions WHERE id = :id"), {"id": juris_id})


@pytest.mark.integration
def test_material_delete_restricted_by_rule(engine, fixture_ids):
    """Deleting a material referenced by a rule must raise (RESTRICT)."""
    juris_id, material_id, source_doc_id = fixture_ids
    with engine.begin() as conn:
        _insert_rule(conn, juris_id, material_id, source_doc_id)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("DELETE FROM materials WHERE id = :id"), {"id": material_id})


@pytest.mark.integration
def test_check_constraint_jurisdiction_type(engine):
    """Inserting an out-of-enum jurisdiction.type must violate ck_jurisdictions_type."""
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO jurisdictions (id, name, slug, type, country, supported_status) "
                "VALUES (:id, 'X', :slug, 'planet', 'US', 'supported')"
            ),
            {"id": uuid.uuid4(), "slug": f"bad-{uuid.uuid4().hex[:8]}"},
        )


@pytest.mark.integration
def test_check_constraint_material_category(engine):
    """Inserting an out-of-enum material.category must violate ck_materials_category."""
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO materials (id, canonical_name, slug, category) "
                "VALUES (:id, 'X', :slug, 'antimatter')"
            ),
            {"id": uuid.uuid4(), "slug": f"bad-{uuid.uuid4().hex[:8]}"},
        )


@pytest.mark.integration
def test_check_constraint_rule_disposition(engine, fixture_ids):
    """Inserting an out-of-enum rule.disposition must violate ck_rules_disposition."""
    juris_id, material_id, source_doc_id = fixture_ids
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO rules "
                "(id, jurisdiction_id, material_id, disposition, accepted_status, "
                " source_document_id, source_quote) "
                "VALUES (:id, :j, :m, 'incinerate', 'accepted', :s, 'q')"
            ),
            {
                "id": uuid.uuid4(),
                "j": juris_id,
                "m": material_id,
                "s": source_doc_id,
            },
        )
