"""Migration round-trip test: upgrade head then downgrade base leaves information_schema clean.

Requires a live Postgres. Uses the DATABASE_URL from the environment (or the default
pointing at the compose app-db). Skipped if the DB is unreachable.
"""
from __future__ import annotations

import contextlib
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
IN_SCOPE_TABLES = {
    "jurisdictions",
    "materials",
    "material_aliases",
    "source_documents",
    "rules",
    "regression_cases",
    "answer_traces",
}


@pytest.fixture(scope="module")
def alembic_cfg(db_url):
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture(scope="module")
def engine(db_url):
    eng = create_engine(db_url)
    yield eng
    eng.dispose()


def _get_public_tables(eng) -> set[str]:
    with eng.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        ).fetchall()
    return {row[0] for row in rows}


@pytest.mark.integration
def test_upgrade_creates_all_seven_tables(alembic_cfg, engine):
    """After upgrade head, all 7 in-scope tables must be present."""
    # Ensure clean state first -- fresh DB has nothing to downgrade.
    with contextlib.suppress(Exception):
        command.downgrade(alembic_cfg, "base")

    command.upgrade(alembic_cfg, "head")

    tables = _get_public_tables(engine)
    missing = IN_SCOPE_TABLES - tables
    assert not missing, f"Tables missing after upgrade: {missing}"

    # Out-of-scope tables must NOT be present.
    out_of_scope = {"facilities", "ingestion_reports", "feedback", "escalations"}
    unexpected = out_of_scope & tables
    assert not unexpected, f"Out-of-scope tables found after upgrade: {unexpected}"


@pytest.mark.integration
def test_downgrade_removes_all_tables(alembic_cfg, engine):
    """After downgrade base, all 7 tables must be gone."""
    # Ensure we start from head.
    command.upgrade(alembic_cfg, "head")

    command.downgrade(alembic_cfg, "base")

    tables = _get_public_tables(engine)
    leftover = IN_SCOPE_TABLES & tables
    assert not leftover, f"Tables still present after downgrade: {leftover}"


@pytest.mark.integration
def test_upgrade_creates_partial_unique_index_on_rules(alembic_cfg, engine):
    """The partial unique index on rules must restrict only NULL-superseded rows.

    Alembic itself guarantees a no-op second upgrade -- testing that adds no signal.
    This instead asserts schema content the migration must produce: a migration that
    drops the WHERE clause or omits the index entirely would silently break the
    one-active-rule-per-(jurisdiction,material) invariant otherwise.
    """
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")

    with engine.connect() as conn:
        index_def = conn.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname = 'public' AND tablename = 'rules' "
                "AND indexname = 'uq_rules_active_per_jurisdiction_material'"
            )
        ).scalar_one_or_none()

    assert index_def is not None, "partial unique index missing from rules table"
    assert "UNIQUE" in index_def.upper()
    assert "superseded_by IS NULL" in index_def
