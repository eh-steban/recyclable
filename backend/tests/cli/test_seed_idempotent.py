"""Idempotency test -- seeding twice should not change row counts or updated_at.

The first run populates all tables.  The second run (identical content) must
not insert new rows and must not bump ``updated_at`` on any existing rows.

We test both conditions:
1. Row counts match between the two runs (no phantom inserts).
2. Every ``updated_at`` value is byte-identical before and after the second run.
"""

from typing import cast

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from src.cli.seed import run_seed

# Row snapshot: (id_text, updated_at_value)
_RowSnapshot = tuple[str, object]


def _row_counts(engine: Engine) -> dict[str, int]:
    tables = (
        "jurisdictions",
        "materials",
        "material_aliases",
        "source_documents",
        "rules",
        "regression_cases",
    )
    counts: dict[str, int] = {}
    with Session(engine) as s:
        for table in tables:
            counts[table] = cast(
                int,
                s.execute(text(f"SELECT count(*) FROM {table}")).scalar(),
            )
    return counts


def _updated_at_snapshot(
    engine: Engine,
) -> dict[str, list[_RowSnapshot]]:
    """Return updated_at values for tables that have that column.

    Only ``jurisdictions`` carries ``updated_at`` in the current schema.
    """
    snapshot: dict[str, list[_RowSnapshot]] = {}
    with Session(engine) as s:
        for table in ("jurisdictions",):
            rows = s.execute(
                text(f"SELECT id::text, updated_at FROM {table} ORDER BY id")
            ).fetchall()
            snapshot[table] = [(cast(str, r[0]), r[1]) for r in rows]
    return snapshot


@pytest.mark.integration
def test_seed_is_idempotent(db_engine: Engine, clean_db: None) -> None:
    """Second seed run produces no new rows and no updated_at changes."""
    _ = clean_db  # injected for DB truncation side effect
    # First run.
    with Session(db_engine) as session, session.begin():
        run_seed("test-fixture", session)

    counts_after_first = _row_counts(db_engine)
    updated_at_after_first = _updated_at_snapshot(db_engine)

    # Second run -- identical content.
    with Session(db_engine) as session, session.begin():
        run_seed("test-fixture", session)

    counts_after_second = _row_counts(db_engine)
    updated_at_after_second = _updated_at_snapshot(db_engine)

    # 1. Row counts must not change.
    for table, before in counts_after_first.items():
        after = counts_after_second.get(table, before)
        assert after == before, (
            f"Table '{table}' count changed from {before} to {after} "
            "on second seed run -- upsert is not idempotent."
        )

    # 2. updated_at must not change for unchanged content.
    for table, before_rows in updated_at_after_first.items():
        after_rows = updated_at_after_second.get(table, before_rows)
        for (before_id, before_ts), (_after_id, after_ts) in zip(
            before_rows, after_rows, strict=True
        ):
            assert before_ts == after_ts, (
                f"Table '{table}' row id={before_id} had updated_at bumped "
                f"from {before_ts} to {after_ts} on second seed run with "
                "unchanged content. IS DISTINCT FROM guard is missing or wrong."
            )
