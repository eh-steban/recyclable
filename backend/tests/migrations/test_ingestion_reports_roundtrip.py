"""Migration round-trip test for ingestion_reports and ingestion_run_traces.

Asserts that migration 0005 creates both tables with correct structure,
and that downgrade removes them and restores the prior state.
"""

import contextlib
import os
import uuid
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import NullPool

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..")

NEW_TABLES = {"ingestion_reports", "ingestion_run_traces"}
PRE_EXISTING_TABLES = {
    "jurisdictions",
    "materials",
    "material_aliases",
    "source_documents",
    "rules",
    "regression_cases",
    "answer_audit_records",
}


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
    eng = create_engine(
        db_url,
        poolclass=NullPool,
        connect_args={"options": "-c lock_timeout=5000"},
    )
    yield eng
    # Restore head so subsequent non-migration tests see the full schema.
    command.upgrade(alembic_cfg, "head")
    eng.dispose()


def _tables(eng: Engine) -> set[str]:
    sql = (
        "SELECT table_name FROM information_schema.tables"
        " WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
    )
    with eng.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
    return {r[0] for r in rows}


def _columns(eng: Engine, table: str) -> set[str]:
    sql = (
        "SELECT column_name FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = :t"
    )
    with eng.connect() as conn:
        rows = conn.execute(text(sql), {"t": table}).fetchall()
    return {r[0] for r in rows}


@pytest.mark.integration
def test_0005_creates_ingestion_tables(
    alembic_cfg: Config, engine: Engine
) -> None:
    """After upgrade head both ingestion tables exist with required columns."""
    with contextlib.suppress(Exception):
        command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")

    tables = _tables(engine)
    missing = NEW_TABLES - tables
    assert not missing, f"Expected ingestion tables missing: {missing}"

    # ingestion_reports column set
    report_cols = _columns(engine, "ingestion_reports")
    required_report_cols = {
        "id",
        "jurisdiction_id",
        "seed_url",
        "source_document_ids",
        "proposed_rule_changes",
        "conflicts",
        "missing_fields",
        "status",
        "reviewer_id",
        "prompt_name",
        "prompt_version",
        "model_id",
        "trace_id",
        "created_at",
        "decided_at",
    }
    missing_cols = required_report_cols - report_cols
    assert not missing_cols, (
        f"ingestion_reports missing columns: {missing_cols}"
    )

    # ingestion_run_traces column set (full D6 set)
    trace_cols = _columns(engine, "ingestion_run_traces")
    required_trace_cols = {
        "id",
        "seed_url",
        "tool_calls",
        "urls_fetched",
        "extraction_outputs",
        "diff_summary",
        "iteration_count",
        "token_count",
        "estimated_cost",
        "errors",
        "source_documents_payload",
        "created_at",
    }
    missing_trace_cols = required_trace_cols - trace_cols
    assert not missing_trace_cols, (
        f"ingestion_run_traces missing columns: {missing_trace_cols}"
    )


@pytest.mark.integration
def test_0005_status_check_constraint(
    alembic_cfg: Config, engine: Engine
) -> None:
    """The status CHECK on ingestion_reports rejects invalid values."""
    command.upgrade(alembic_cfg, "head")

    jur_id = uuid.uuid4()
    trace_id = uuid.uuid4()

    _insert_jur = (
        "INSERT INTO jurisdictions"
        " (id, name, slug, type, country, supported_status)"
        " VALUES (:id, 'Test', 'test-jur', 'city', 'US', 'supported')"
    )
    _insert_trace = (
        "INSERT INTO ingestion_run_traces (id, seed_url)"
        " VALUES (:id, 'https://example.com')"
    )
    _insert_report_ok = (
        "INSERT INTO ingestion_reports"
        " (id, jurisdiction_id, seed_url, status, trace_id)"
        " VALUES (:id, :jur, 'https://example.com', 'draft', :trace)"
    )
    _insert_report_bad = (
        "INSERT INTO ingestion_reports"
        " (id, jurisdiction_id, seed_url, status, trace_id)"
        " VALUES (:id, :jur, 'https://example.com', 'bad_status', :trace)"
    )

    with engine.begin() as conn:
        conn.execute(text(_insert_jur), {"id": jur_id})
        conn.execute(text(_insert_trace), {"id": trace_id})
        conn.execute(
            text(_insert_report_ok),
            {"id": uuid.uuid4(), "jur": jur_id, "trace": trace_id},
        )

    # Invalid status must fail the CHECK constraint
    with (
        engine.begin() as conn,
        pytest.raises(Exception, match="ingestion_reports_status"),
    ):
        conn.execute(
            text(_insert_report_bad),
            {"id": uuid.uuid4(), "jur": jur_id, "trace": trace_id},
        )


@pytest.mark.integration
def test_0005_downgrade_removes_ingestion_tables(
    alembic_cfg: Config, engine: Engine
) -> None:
    """After downgrade to 0004 both ingestion tables are gone."""
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "0004_pg_trgm_index")

    tables = _tables(engine)
    leftover = NEW_TABLES & tables
    assert not leftover, (
        f"Ingestion tables still present after downgrade: {leftover}"
    )
    # Pre-existing tables must be unaffected
    missing_prior = PRE_EXISTING_TABLES - tables
    assert not missing_prior, (
        f"Pre-existing tables were unexpectedly dropped: {missing_prior}"
    )
