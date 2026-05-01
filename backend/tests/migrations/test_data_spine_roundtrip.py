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
def test_double_upgrade_is_idempotent(alembic_cfg, engine):
    """Running upgrade head twice should not error (no-op on second run)."""
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")
    command.upgrade(alembic_cfg, "head")  # second run -- should be a no-op

    tables = _get_public_tables(engine)
    assert IN_SCOPE_TABLES.issubset(tables)
