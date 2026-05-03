"""Schema mismatch tests -- malformed YAML raises before any DB write.

These tests are pure domain tests (no DB needed) for the parsing
functions.  We also include integration tests that confirm zero rows
are written when the parse raises.
"""

from __future__ import annotations

import pathlib
from typing import cast

import pytest
import yaml
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.domain.exceptions import EntityNotFoundError, SeedSchemaError

# ---- Pure-domain parse tests (no DB) ----


def test_jurisdiction_wrong_type_raises_seed_schema_error() -> None:
    """An invalid ``type`` value should raise ``SeedSchemaError``."""
    from app.cli._seed_parse import parse_jurisdictions  # noqa: PLC0415

    bad_data = [
        {
            "slug": "test",
            "name": "Test",
            "type": "village",  # not in JurisdictionType enum
            "country": "US",
            "supported_status": "supported",
        }
    ]
    with pytest.raises(SeedSchemaError):
        _ = parse_jurisdictions(bad_data, "test-dataset")


def test_jurisdiction_top_level_not_list_raises() -> None:
    """A dict at top level instead of a list raises ``SeedSchemaError``."""
    from app.cli._seed_parse import parse_jurisdictions  # noqa: PLC0415

    with pytest.raises(SeedSchemaError):
        _ = parse_jurisdictions({"slug": "test"}, "test-dataset")


def test_material_invalid_category_raises() -> None:
    """An invalid ``category`` should raise ``SeedSchemaError``."""
    from app.cli._seed_parse import parse_materials  # noqa: PLC0415

    bad_data = [
        {
            "slug": "mystery",
            "canonical_name": "Mystery",
            "category": "mystery_category",  # not in MaterialCategory
        }
    ]
    with pytest.raises(SeedSchemaError):
        _ = parse_materials(bad_data, "test-dataset")


def test_rule_missing_jurisdiction_raises() -> None:
    """A rule without a ``jurisdiction`` field raises ``SeedSchemaError``."""
    from app.cli._seed_parse import parse_rules  # noqa: PLC0415

    bad_rule = [
        {
            "slug": "test-rule",
            # no 'jurisdiction' key
            "material": "some-mat",
            "source_document": "some-doc",
            "disposition": "curbside_recycle",
            "accepted_status": "accepted",
            "source_quote": "some quote",
        }
    ]
    with pytest.raises(SeedSchemaError):
        _ = parse_rules(bad_rule, "test-dataset", {}, {}, {})


def test_rule_invalid_disposition_raises() -> None:
    """A rule with an invalid ``disposition`` raises ``SeedSchemaError``."""
    from app.cli._seed_parse import parse_rules  # noqa: PLC0415
    from app.domain.models.jurisdiction import (  # noqa: PLC0415
        Jurisdiction,
        JurisdictionType,
        SupportedStatus,
    )
    from app.domain.models.material import (  # noqa: PLC0415
        Material,
        MaterialCategory,
    )
    from app.domain.models.source_document import (  # noqa: PLC0415
        SourceDocument,
    )

    jur = Jurisdiction(
        slug="j",
        name="J",
        type=JurisdictionType.CITY,
        country="US",
        supported_status=SupportedStatus.SUPPORTED,
    )
    mat = Material(
        slug="m", canonical_name="M", category=MaterialCategory.METAL
    )
    doc = SourceDocument(
        jurisdiction_id=jur.id,
        url="https://example.com",
        title="T",
        authority_level=1,
        source_text="Valid source text with the quote here.",
        source_text_hash="x",
    )
    bad_rule = [
        {
            "slug": "bad-rule",
            "jurisdiction": "j",
            "material": "m",
            "source_document": "https://example.com",
            "disposition": "teleport",  # invalid
            "accepted_status": "accepted",
            "source_quote": "Valid source text with the quote here.",
        }
    ]
    with pytest.raises(SeedSchemaError):
        _ = parse_rules(
            bad_rule,
            "test-dataset",
            {"j": jur},
            {"m": mat},
            {"https://example.com": doc},
        )


def test_rules_invalid_enum_raises_seed_schema_error() -> None:
    """A rule with a bad ``accepted_status`` enum raises SeedSchemaError."""
    from app.cli._seed_parse import parse_rules  # noqa: PLC0415
    from app.domain.models.jurisdiction import (  # noqa: PLC0415
        Jurisdiction,
        JurisdictionType,
        SupportedStatus,
    )
    from app.domain.models.material import (  # noqa: PLC0415
        Material,
        MaterialCategory,
    )
    from app.domain.models.source_document import (  # noqa: PLC0415
        SourceDocument,
    )

    jur = Jurisdiction(
        slug="j2",
        name="J2",
        type=JurisdictionType.CITY,
        country="US",
        supported_status=SupportedStatus.SUPPORTED,
    )
    mat = Material(
        slug="m2", canonical_name="M2", category=MaterialCategory.PAPER
    )
    doc = SourceDocument(
        jurisdiction_id=jur.id,
        url="https://example.com/doc2",
        title="Doc2",
        authority_level=1,
        source_text="Some text with a valid quote inside it.",
        source_text_hash="y",
    )
    bad_rule = [
        {
            "slug": "enum-bad-rule",
            "jurisdiction": "j2",
            "material": "m2",
            "source_document": "https://example.com/doc2",
            "disposition": "curbside_recycle",
            "accepted_status": "maybe",  # invalid enum value
            "source_quote": "Some text with a valid quote inside it.",
        }
    ]
    with pytest.raises(SeedSchemaError):
        _ = parse_rules(
            bad_rule,
            "test-dataset",
            {"j2": jur},
            {"m2": mat},
            {"https://example.com/doc2": doc},
        )


def test_rule_unknown_jurisdiction_slug_raises_entity_not_found() -> None:
    """Unknown jurisdiction slug in a rule raises EntityNotFoundError."""
    from app.cli._seed_parse import parse_rules  # noqa: PLC0415

    bad_rule = [
        {
            "slug": "ghost-rule",
            "jurisdiction": "ghost-city",  # not in map
            "material": "some-mat",
            "source_document": "https://example.com",
            "disposition": "curbside_recycle",
            "accepted_status": "accepted",
            "source_quote": "irrelevant",
        }
    ]
    with pytest.raises(EntityNotFoundError):
        _ = parse_rules(bad_rule, "test-dataset", {}, {}, {})


def test_rule_unknown_material_slug_raises_entity_not_found() -> None:
    """Unknown material slug in a rule raises EntityNotFoundError."""
    from app.cli._seed_parse import parse_rules  # noqa: PLC0415
    from app.domain.models.jurisdiction import (  # noqa: PLC0415
        Jurisdiction,
        JurisdictionType,
        SupportedStatus,
    )

    jur = Jurisdiction(
        slug="j3",
        name="J3",
        type=JurisdictionType.CITY,
        country="US",
        supported_status=SupportedStatus.SUPPORTED,
    )
    bad_rule = [
        {
            "slug": "ghost-mat-rule",
            "jurisdiction": "j3",
            "material": "ghost-material",  # not in map
            "source_document": "https://example.com",
            "disposition": "curbside_recycle",
            "accepted_status": "accepted",
            "source_quote": "irrelevant",
        }
    ]
    with pytest.raises(EntityNotFoundError):
        _ = parse_rules(bad_rule, "test-dataset", {"j3": jur}, {}, {})


def test_rule_unknown_source_document_raises_entity_not_found() -> None:
    """Unknown source_document URL in a rule raises EntityNotFoundError."""
    from app.cli._seed_parse import parse_rules  # noqa: PLC0415
    from app.domain.models.jurisdiction import (  # noqa: PLC0415
        Jurisdiction,
        JurisdictionType,
        SupportedStatus,
    )
    from app.domain.models.material import (  # noqa: PLC0415
        Material,
        MaterialCategory,
    )

    jur = Jurisdiction(
        slug="j4",
        name="J4",
        type=JurisdictionType.CITY,
        country="US",
        supported_status=SupportedStatus.SUPPORTED,
    )
    mat = Material(
        slug="m4", canonical_name="M4", category=MaterialCategory.METAL
    )
    bad_rule = [
        {
            "slug": "ghost-src-rule",
            "jurisdiction": "j4",
            "material": "m4",
            # not in source_doc map
            "source_document": "https://ghost.example.com/not-there",
            "disposition": "curbside_recycle",
            "accepted_status": "accepted",
            "source_quote": "irrelevant",
        }
    ]
    with pytest.raises(EntityNotFoundError):
        _ = parse_rules(bad_rule, "test-dataset", {"j4": jur}, {"m4": mat}, {})


def test_parse_source_documents_missing_jurisdiction_raises() -> None:
    """Missing ``jurisdiction`` in source document raises SeedSchemaError."""
    from app.cli._seed_parse import parse_source_documents  # noqa: PLC0415

    bad_data = [
        {
            # no 'jurisdiction' key
            "url": "https://example.com/doc",
            "title": "Some Doc",
            "authority_level": 1,
            "source_text": "Some text.",
        }
    ]
    with pytest.raises(SeedSchemaError, match="missing 'jurisdiction'"):
        _ = parse_source_documents(bad_data, "test-dataset", {})


def test_regression_cases_unknown_jurisdiction_raises_entity_not_found() -> (
    None
):
    """Unknown jurisdiction slug in regression case raises EntityNotFoundError.

    Not SeedSchemaError -- a missing entity, not a schema problem.
    """
    from app.cli._seed_parse import parse_regression_cases  # noqa: PLC0415

    bad_data = [
        {
            "query": "Test query?",
            "jurisdiction": "no-such-city",
            "expected_status": "accepted",
            "expected_disposition": "curbside_recycle",
            "must_cite_source": True,
            "refusal_required": False,
        }
    ]
    with pytest.raises(EntityNotFoundError):
        _ = parse_regression_cases(bad_data, "test-dataset", {}, {})


def test_regression_cases_unknown_material_raises_entity_not_found() -> None:
    """Unknown material slug in a regression case raises EntityNotFoundError."""
    from app.cli._seed_parse import parse_regression_cases  # noqa: PLC0415
    from app.domain.models.jurisdiction import (  # noqa: PLC0415
        Jurisdiction,
        JurisdictionType,
        SupportedStatus,
    )

    jur = Jurisdiction(
        slug="j5",
        name="J5",
        type=JurisdictionType.CITY,
        country="US",
        supported_status=SupportedStatus.SUPPORTED,
    )
    bad_data = [
        {
            "query": "Test query?",
            "jurisdiction": "j5",
            "material": "ghost-material",  # not in material map
            "expected_status": "accepted",
            "expected_disposition": "curbside_recycle",
            "must_cite_source": True,
            "refusal_required": False,
        }
    ]
    with pytest.raises(EntityNotFoundError):
        _ = parse_regression_cases(bad_data, "test-dataset", {"j5": jur}, {})


# ---- Dataset path traversal (no DB) ----


def test_path_traversal_exits_nonzero(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A --dataset value that escapes seeds_root causes sys.exit(1)."""
    _ = monkeypatch  # unused but kept for fixture symmetry
    from app.cli._seed_parse import validate_dataset_path  # noqa: PLC0415

    seeds_root = tmp_path / "seeds"
    seeds_root.mkdir()

    with pytest.raises(SystemExit) as exc_info:
        _ = validate_dataset_path("../etc", seeds_root)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "resolves outside seeds directory" in captured.err


# ---- Integration test: no DB writes on schema error ----


@pytest.mark.integration
def test_schema_error_before_db_write(
    db_engine: Engine,
    clean_db: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """Malformed jurisdiction.yaml raises SeedSchemaError before DB write."""
    _ = clean_db  # injected for DB truncation side effect
    import app.cli.seed as seed_module  # noqa: PLC0415

    monkeypatch.setattr(seed_module, "_SEEDS_ROOT", tmp_path)

    dataset_name = "malformed-test"
    dataset_dir = tmp_path / dataset_name
    dataset_dir.mkdir()

    # Write a jurisdiction file with an invalid type.
    _ = (dataset_dir / "jurisdiction.yaml").write_text(
        yaml.dump(
            [
                {
                    "slug": "bad-jur",
                    "name": "Bad Jur",
                    "type": "galactic_empire",  # invalid
                    "country": "US",
                    "supported_status": "supported",
                }
            ]
        ),
        encoding="utf-8",
    )
    # Other files must exist and be valid YAML but are irrelevant.
    for fname in ("source_documents.yaml", "materials.yaml", "rules.yaml"):
        _ = (dataset_dir / fname).write_text(yaml.dump([]), encoding="utf-8")

    from app.cli.seed import run_seed  # noqa: PLC0415

    with (
        pytest.raises(SeedSchemaError),
        Session(db_engine) as session,
        session.begin(),
    ):
        run_seed(dataset_name, session)

    # All four core tables must be empty.
    with Session(db_engine) as session:
        for table, col, val in [
            ("jurisdictions", "slug", "bad-jur"),
            ("materials", "slug", "bad-jur"),
            ("source_documents", "url", "https://bad-jur.example.com"),
            ("rules", "accepted_status", "accepted"),
        ]:
            count = cast(
                int,
                session.execute(
                    text(f"SELECT count(*) FROM {table} WHERE {col} = :v"),
                    {"v": val},
                ).scalar(),
            )
            assert count == 0, (
                f"Table '{table}' has rows after a failed schema-error run."
            )


@pytest.mark.integration
def test_rules_schema_error_leaves_all_tables_empty(
    db_engine: Engine,
    clean_db: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """Malformed rules.yaml (bad enum) rolls back all tables, not just rules."""
    _ = clean_db  # injected for DB truncation side effect
    import app.cli.seed as seed_module  # noqa: PLC0415

    monkeypatch.setattr(seed_module, "_SEEDS_ROOT", tmp_path)

    dataset_name = "rules-malformed-test"
    dataset_dir = tmp_path / dataset_name
    dataset_dir.mkdir()

    _ = (dataset_dir / "jurisdiction.yaml").write_text(
        yaml.dump(
            [
                {
                    "slug": "rm-city",
                    "name": "RM City",
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
                    "jurisdiction": "rm-city",
                    "url": "https://rm.example.com/guide",
                    "title": "RM Guide",
                    "authority_level": 1,
                    "source_text": "Aluminum cans are recyclable here.",
                }
            ]
        ),
        encoding="utf-8",
    )
    _ = (dataset_dir / "materials.yaml").write_text(
        yaml.dump(
            [
                {
                    "slug": "rm-cans",
                    "canonical_name": "RM Aluminum Can",
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
                    "slug": "rm-cans-rule",
                    "jurisdiction": "rm-city",
                    "material": "rm-cans",
                    "source_document": "https://rm.example.com/guide",
                    "disposition": "curbside_recycle",
                    "accepted_status": "maybe",  # invalid enum
                    "source_quote": "Aluminum cans are recyclable here.",
                }
            ]
        ),
        encoding="utf-8",
    )

    from app.cli.seed import run_seed  # noqa: PLC0415

    with (
        pytest.raises(SeedSchemaError),
        Session(db_engine) as session,
        session.begin(),
    ):
        run_seed(dataset_name, session)

    # All four tables must be empty after the failed run.
    _jur_sql = "SELECT count(*) FROM jurisdictions WHERE slug = 'rm-city'"
    _mat_sql = "SELECT count(*) FROM materials WHERE slug = 'rm-cans'"
    _src_sql = (
        "SELECT count(*) FROM source_documents"
        " WHERE url = 'https://rm.example.com/guide'"
    )
    _rule_sql = "SELECT count(*) FROM rules"
    with Session(db_engine) as session:
        jur_count = cast(int, session.execute(text(_jur_sql)).scalar())
        mat_count = cast(int, session.execute(text(_mat_sql)).scalar())
        src_count = cast(int, session.execute(text(_src_sql)).scalar())
        rule_count = cast(int, session.execute(text(_rule_sql)).scalar())

    assert jur_count == 0, (
        f"jurisdictions has {jur_count} row(s) after failed rules parse"
    )
    assert mat_count == 0, (
        f"materials has {mat_count} row(s) after failed rules parse"
    )
    assert src_count == 0, (
        f"source_documents has {src_count} row(s) after failed rules parse"
    )
    assert rule_count == 0, (
        f"rules has {rule_count} row(s) after failed rules parse"
    )
