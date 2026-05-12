"""Atomicity test -- a mid-load failure must leave zero partial rows.

We inject a failure by monkey-patching the rule repository's ``upsert``
to raise after jurisdictions and materials have been written.  The
transaction must roll back, leaving all tables empty.
"""

import pathlib
from typing import cast

import pytest
import yaml
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session


def _write_minimal_dataset(dataset_dir: pathlib.Path) -> None:
    """Write a two-rule dataset to *dataset_dir*."""
    _ = (dataset_dir / "jurisdiction.yaml").write_text(
        yaml.dump(
            [
                {
                    "slug": "atomic-city",
                    "name": "Atomic City",
                    "type": "city",
                    "country": "US",
                    "supported_status": "supported",
                }
            ]
        ),
        encoding="utf-8",
    )
    _ = (dataset_dir / "source_documents.yaml").write_text(
        yaml.dump(
            [
                {
                    "jurisdiction": "atomic-city",
                    "url": "https://atomic.example.com/recycling",
                    "title": "Atomic City Recycling",
                    "authority_level": 1,
                    "source_text": "Cans are accepted. Bags are rejected.",
                }
            ]
        ),
        encoding="utf-8",
    )
    _ = (dataset_dir / "materials.yaml").write_text(
        yaml.dump(
            [
                {
                    "slug": "atomic-cans",
                    "canonical_name": "Atomic Can",
                    "category": "metal",
                }
            ]
        ),
        encoding="utf-8",
    )
    _ = (dataset_dir / "rules.yaml").write_text(
        yaml.dump(
            [
                {
                    "slug": "atomic-city-cans",
                    "jurisdiction": "atomic-city",
                    "material": "atomic-cans",
                    "source_document": "https://atomic.example.com/recycling",
                    "disposition": "curbside_recycle",
                    "accepted_status": "accepted",
                    "source_quote": "Cans are accepted.",
                    "confidence": "high",
                }
            ]
        ),
        encoding="utf-8",
    )


@pytest.mark.integration
def test_mid_load_failure_rolls_back_all_rows(
    db_engine: Engine,
    clean_db: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """Injecting a failure during rule upsert leaves no rows in any table."""
    _ = clean_db  # injected for DB truncation side effect
    import src.cli.seed as seed_module  # noqa: PLC0415
    import src.infra.db.repos.rule_repo as rule_repo_module  # noqa: PLC0415

    monkeypatch.setattr(seed_module, "_SEEDS_ROOT", tmp_path)

    dataset_name = "atomic-test"
    dataset_dir = tmp_path / dataset_name
    dataset_dir.mkdir()
    _write_minimal_dataset(dataset_dir)

    # Inject failure: rule upsert raises RuntimeError.
    def boom(
        _self: rule_repo_module.SqlRuleRepo,
        _rule: object,
    ) -> None:
        raise RuntimeError("injected mid-load failure")

    monkeypatch.setattr(rule_repo_module.SqlRuleRepo, "upsert", boom)

    from src.cli.seed import run_seed  # noqa: PLC0415

    with (
        pytest.raises(RuntimeError, match="injected mid-load failure"),
        Session(db_engine) as session,
        session.begin(),
    ):
        run_seed(dataset_name, session)

    # All tables must be empty -- transaction rolled back.
    with Session(db_engine) as session:
        for table, col, value in [
            ("jurisdictions", "slug", "atomic-city"),
            ("materials", "slug", "atomic-cans"),
            ("source_documents", "url", "https://atomic.example.com/recycling"),
            ("rules", "accepted_status", "accepted"),
        ]:
            count = cast(
                int,
                session.execute(
                    text(f"SELECT count(*) FROM {table} WHERE {col} = :v"),
                    {"v": value},
                ).scalar(),
            )
            assert count == 0, (
                f"Table '{table}' has {count} row(s) after a"
                " rolled-back transaction. Atomicity violated."
            )
