"""Verifier exit-code tests.

Covers:

1. Empty DB -- all acceptance queries return 0, so verifier exits nonzero.
2. Seeded DB (test-fixture) -- table-count passes but Denver-specific
   acceptance queries fail, so run_verify returns False overall.
3. Broken row (corrupted source_text) -- quote-integrity check fails.
4. Happy path -- seeding the synthetic verify-fixture dataset satisfies
   all 6 acceptance queries; run_verify returns True.
5. Bad distribution -- all 8 regression cases in 'accepted' causes the
   distribution check to fail.
"""

import pathlib

import pytest
import yaml
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from src.cli.verify import run_verify


@pytest.mark.integration
def test_empty_db_exits_nonzero(
    db_engine: Engine,
    clean_db: None,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_verify returns False when the DB has no seed data."""
    _ = clean_db  # injected for DB truncation side effect
    import src.cli.verify as verify_module  # noqa: PLC0415

    monkeypatch.setattr(verify_module, "_SEEDS_ROOT", tmp_path)

    # Create minimal fixture dir so fixture-parse step completes.
    dataset_dir = tmp_path / "empty-verify-test"
    dataset_dir.mkdir()
    for fname in (
        "jurisdiction.yaml",
        "source_documents.yaml",
        "materials.yaml",
        "rules.yaml",
    ):
        _ = (dataset_dir / fname).write_text(yaml.dump([]), encoding="utf-8")

    with Session(db_engine) as session:
        passed = run_verify("empty-verify-test", session)

    assert not passed, "Expected run_verify to return False for an empty DB"


@pytest.mark.integration
def test_seeded_db_partial_pass(
    db_engine: Engine,
    clean_db: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """After loading test-fixture, table-count passes but Denver-specific
    acceptance queries fail, so run_verify returns False overall."""
    _ = clean_db  # injected for DB truncation side effect
    _ = tmp_path  # unused in this test but kept for fixture symmetry
    import src.cli.seed as seed_module  # noqa: PLC0415
    import src.cli.verify as verify_module  # noqa: PLC0415

    # Point both modules at the real seeds directory.
    real_seeds = pathlib.Path(__file__).parents[2] / "seeds"
    monkeypatch.setattr(seed_module, "_SEEDS_ROOT", real_seeds)
    monkeypatch.setattr(verify_module, "_SEEDS_ROOT", real_seeds)

    from src.cli.seed import run_seed  # noqa: PLC0415

    with Session(db_engine) as session, session.begin():
        run_seed("test-fixture", session)

    with Session(db_engine) as session:
        passed = run_verify("test-fixture", session)

    # The test-fixture has no 'denver-co-us' jurisdiction, so the Denver
    # acceptance checks will fail.  run_verify must return False.
    assert not passed, (
        "Expected run_verify to return False -- test-fixture lacks Denver data"
    )


@pytest.mark.integration
def test_broken_row_triggers_quote_integrity_failure(
    db_engine: Engine,
    clean_db: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """Manually inserting a rule whose quote is not in source_text causes
    the quote-integrity check to fail."""
    _ = clean_db  # injected for DB truncation side effect
    _ = tmp_path  # unused in this test but kept for fixture symmetry
    import src.cli.seed as seed_module  # noqa: PLC0415
    import src.cli.verify as verify_module  # noqa: PLC0415

    real_seeds = pathlib.Path(__file__).parents[2] / "seeds"
    monkeypatch.setattr(seed_module, "_SEEDS_ROOT", real_seeds)
    monkeypatch.setattr(verify_module, "_SEEDS_ROOT", real_seeds)

    from src.cli.seed import run_seed  # noqa: PLC0415

    # Seed normally first.
    with Session(db_engine) as session, session.begin():
        run_seed("test-fixture", session)

    # Corrupt a source_document's text so quotes no longer match.
    _corrupt_sql = (
        "UPDATE source_documents"
        " SET source_text = 'Completely different text.'"
        " WHERE url = 'https://example.com/recycling'"
    )
    with Session(db_engine) as session, session.begin():
        _ = session.execute(text(_corrupt_sql))

    with Session(db_engine) as session:
        passed = run_verify("test-fixture", session)

    assert not passed, (
        "Expected run_verify to return False after corrupting source_text"
    )


@pytest.mark.integration
def test_verify_fixture_passes_all_checks(
    db_engine: Engine,
    clean_db: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seeding the verify-fixture dataset satisfies all acceptance queries.

    The verify-fixture uses slug='denver-co-us' (matching the acceptance
    queries) but contains only synthetic placeholder content -- it is not
    real Denver data.
    """
    _ = clean_db  # injected for DB truncation side effect
    import src.cli.seed as seed_module  # noqa: PLC0415
    import src.cli.verify as verify_module  # noqa: PLC0415

    real_seeds = pathlib.Path(__file__).parents[2] / "seeds"
    monkeypatch.setattr(seed_module, "_SEEDS_ROOT", real_seeds)
    monkeypatch.setattr(verify_module, "_SEEDS_ROOT", real_seeds)

    from src.cli.seed import run_seed  # noqa: PLC0415

    with Session(db_engine) as session, session.begin():
        run_seed("verify-fixture", session)

    with Session(db_engine) as session:
        passed = run_verify("verify-fixture", session)

    assert passed, (
        "Expected run_verify to return True for the verify-fixture dataset -- "
        "all acceptance queries should pass."
    )


@pytest.mark.integration
def test_bad_distribution_fails_verifier(
    db_engine: Engine,
    clean_db: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """All 8 regression cases in 'accepted' fails the distribution check."""
    _ = clean_db  # injected for DB truncation side effect
    _ = tmp_path  # unused in this test but kept for fixture symmetry
    import src.cli.seed as seed_module  # noqa: PLC0415
    import src.cli.verify as verify_module  # noqa: PLC0415

    # Use the verify-fixture to get a well-formed DB first, then corrupt it.
    real_seeds = pathlib.Path(__file__).parents[2] / "seeds"
    monkeypatch.setattr(seed_module, "_SEEDS_ROOT", real_seeds)
    monkeypatch.setattr(verify_module, "_SEEDS_ROOT", real_seeds)

    from src.cli.seed import run_seed  # noqa: PLC0415

    with Session(db_engine) as session, session.begin():
        run_seed("verify-fixture", session)

    # Override all regression cases: expected_status='accepted',
    # refusal_required=false. Puts 8 in 'accepted', 0 in others.
    _override_sql = (
        "UPDATE regression_cases"
        " SET expected_status = 'accepted', refusal_required = false"
    )
    with Session(db_engine) as session, session.begin():
        _ = session.execute(text(_override_sql))

    with Session(db_engine) as session:
        passed = run_verify("verify-fixture", session)

    assert not passed, (
        "Expected run_verify to return False when all 8 cases are 'accepted'"
        " (distribution check must fail for rejected/conditional/"
        "refusal_required)"
    )
