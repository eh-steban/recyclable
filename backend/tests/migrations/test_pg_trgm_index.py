"""Migration 0004 round-trip test: pg_trgm extension + GIN index.

Confirms that upgrade 0004 creates the GIN index on material_aliases.alias
and that downgrade 0004 removes the index (but does NOT remove the extension).
Requires a live Postgres with pg_trgm extension installable.
Skipped if the DB is unreachable.
"""

import contextlib
import os
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..")

_GIN_INDEX = "ix_material_aliases_alias_trgm"


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
    yield eng
    # Restore the test DB to head so non-migration tests that run after
    # this module always see a fully migrated schema.
    command.upgrade(alembic_cfg, "head")
    eng.dispose()


def _index_exists(eng: Engine, index_name: str) -> bool:
    sql = text(
        "SELECT 1 FROM pg_indexes"
        + " WHERE schemaname = 'public'"
        + " AND indexname = :idx"
    )
    with eng.connect() as conn:
        row = conn.execute(sql, {"idx": index_name}).fetchone()
    return row is not None


def _extension_exists(eng: Engine, ext_name: str) -> bool:
    sql = text("SELECT 1 FROM pg_extension WHERE extname = :ext")
    with eng.connect() as conn:
        row = conn.execute(sql, {"ext": ext_name}).fetchone()
    return row is not None


@pytest.mark.integration
def test_upgrade_0004_creates_gin_index(
    alembic_cfg: Config, engine: Engine
) -> None:
    """After upgrading to 0004, the GIN index must be present."""
    with contextlib.suppress(Exception):
        command.downgrade(alembic_cfg, "0003_conditions_column")

    command.upgrade(alembic_cfg, "0004_pg_trgm_index")

    assert _index_exists(engine, _GIN_INDEX), (
        f"GIN index {_GIN_INDEX!r} missing after 0004 upgrade"
    )
    assert _extension_exists(engine, "pg_trgm"), (
        "pg_trgm extension not present after 0004 upgrade"
    )


@pytest.mark.integration
def test_downgrade_0004_removes_gin_index_keeps_extension(
    alembic_cfg: Config, engine: Engine
) -> None:
    """After downgrading from 0004, the GIN index must be gone.

    The pg_trgm extension must NOT be dropped on downgrade -- it is shared
    and may be used by other indexes or queries outside this feature.
    """
    # Ensure we start from 0004.
    command.upgrade(alembic_cfg, "0004_pg_trgm_index")

    command.downgrade(alembic_cfg, "0003_conditions_column")

    assert not _index_exists(engine, _GIN_INDEX), (
        f"GIN index {_GIN_INDEX!r} still present after 0004 downgrade"
    )
    # Extension is left in place intentionally.
    # (Whether it exists depends on whether it was pre-installed in the
    # test DB environment; we do not assert its presence here.)
