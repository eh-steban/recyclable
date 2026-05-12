"""ORM introspection test for AnswerAuditRecordORM.

Asserts the D6 column set per the Phase 2 design (Step 2 rename +
AnswerAuditRecord column reshape). Pure in-process test -- no DB
connection required.

This test is written first (TDD red record) before the production code
change so that it fails on the pre-rename tree and passes only after:
 - 2.1 rename (backend/app/ -> backend/src/)
 - 2.2 ORM rewrite (AnswerAuditRecordORM with D6 column set)
 - Imports rewritten to src.*
"""

from __future__ import annotations

import pytest


def _get_column_names(orm_cls: type) -> set[str]:
    """Return the set of column attribute names on an ORM class."""
    from sqlalchemy import inspect as sa_inspect

    mapper = sa_inspect(orm_cls)
    return {col.key for col in mapper.columns}


def test_answer_audit_record_orm_importable() -> None:
    """AnswerAuditRecordORM must be importable from src.infra.db.models."""
    from src.infra.db.models.answer_audit_record import (
        AnswerAuditRecordORM,  # noqa: PLC0415
    )

    assert AnswerAuditRecordORM.__tablename__ == "answer_audit_records"


def test_answer_audit_record_orm_d6_columns() -> None:
    """AnswerAuditRecordORM must carry the exact D6 column set.

    Column set per design D6:
      id, query_text, query_location_input, jurisdiction_id (FK),
      verdict (enum), outcome_kind (enum), no_evaluation_reason
      (nullable enum), recommended_action, citations (JSONB),
      validator_findings (JSONB), prompt_version, model_id,
      latency_ms, created_at.

    Touches INV-PROD-003 (Postgres is the single source of truth):
    the ORM must reflect the canonical audit schema.
    """
    from src.infra.db.models.answer_audit_record import (
        AnswerAuditRecordORM,  # noqa: PLC0415
    )

    expected = {
        "id",
        "query_text",
        "query_location_input",
        "jurisdiction_id",
        "verdict",
        "outcome_kind",
        "no_evaluation_reason",
        "recommended_action",
        "citations",
        "validator_findings",
        "prompt_version",
        "model_id",
        "latency_ms",
        "created_at",
    }

    actual = _get_column_names(AnswerAuditRecordORM)
    missing = expected - actual
    extra = actual - expected

    assert not missing, f"AnswerAuditRecordORM is missing D6 columns: {missing}"
    assert not extra, (
        f"AnswerAuditRecordORM has unexpected extra columns: {extra}"
    )


@pytest.mark.parametrize(
    "col_name",
    ["verdict", "outcome_kind", "no_evaluation_reason"],
)
def test_answer_audit_record_orm_enum_columns_exist(col_name: str) -> None:
    """Each enum column must exist on the ORM (type checked separately)."""
    from src.infra.db.models.answer_audit_record import (
        AnswerAuditRecordORM,  # noqa: PLC0415
    )

    cols = _get_column_names(AnswerAuditRecordORM)
    assert col_name in cols, (
        f"Expected enum column {col_name!r} not found on AnswerAuditRecordORM"
    )


def test_answer_audit_record_orm_jsonb_columns() -> None:
    """citations and validator_findings must be JSONB columns."""
    from sqlalchemy import inspect as sa_inspect  # noqa: PLC0415
    from sqlalchemy.dialects.postgresql import JSONB  # noqa: PLC0415

    from src.infra.db.models.answer_audit_record import (
        AnswerAuditRecordORM,  # noqa: PLC0415
    )

    mapper = sa_inspect(AnswerAuditRecordORM)
    col_map = {col.key: col for col in mapper.columns}

    for jsonb_col in ("citations", "validator_findings"):
        assert jsonb_col in col_map, (
            f"Expected JSONB column {jsonb_col!r} not found"
        )
        assert isinstance(col_map[jsonb_col].type, JSONB), (
            f"Column {jsonb_col!r} is not JSONB"
        )


def test_answer_audit_record_orm_no_evaluation_reason_nullable() -> None:
    """no_evaluation_reason is nullable (absent for evaluated paths)."""
    from sqlalchemy import inspect as sa_inspect  # noqa: PLC0415

    from src.infra.db.models.answer_audit_record import (
        AnswerAuditRecordORM,  # noqa: PLC0415
    )

    mapper = sa_inspect(AnswerAuditRecordORM)
    col_map = {col.key: col for col in mapper.columns}

    col = col_map["no_evaluation_reason"]
    assert col.nullable, "no_evaluation_reason must be nullable"
