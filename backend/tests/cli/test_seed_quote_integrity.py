"""Quote-integrity tests for the seed loader.

Two scenarios:

1. A rule with *curly* quotes in ``source_quote`` that are a normalized
   substring of a source with *straight* quotes -- must pass.
2. A rule whose ``source_quote`` does not appear in the source text at
   all -- must raise ``SeedIntegrityError`` before any DB write.
"""

from __future__ import annotations

import pathlib
from typing import cast

import pytest
import yaml
from sqlalchemy import Engine

from src.domain.exceptions import SeedIntegrityError
from src.domain.quote_normalize import normalize

# Unicode curly quote characters as constants to avoid literal embedding.
_LQUOTE = "“"  # left double quotation mark
_RQUOTE = "”"  # right double quotation mark


# ---- Pure-domain tests (no DB required) ----


def test_curly_quote_variant_passes_after_normalization():
    """Curly double quotes in source_quote match straight-quoted source_text."""
    # Source text uses straight double quotes around the material name.
    source_text = 'Aluminum cans are accepted for "curbside recycling".'
    # The fixture quote uses curly double quotes (U+201C, U+201D) around the
    # same span -- normalizer straightens them so the substring check passes.
    source_quote = _LQUOTE + "curbside recycling" + _RQUOTE
    # After normalization: '"curbside recycling"' in source_text.
    assert normalize(source_quote) in normalize(source_text)


def test_substring_mismatch_fails():
    """A quote that genuinely does not appear in source_text must not match."""
    source_text = "Aluminum cans are accepted for curbside recycling."
    source_quote = "Plastic bags are NOT accepted anywhere."
    assert normalize(source_quote) not in normalize(source_text)


# ---- Integration tests (DB required) ----


def _make_dataset(
    tmp_path: pathlib.Path,
    source_text: str,
    source_quote: str,
) -> str:
    """Write a minimal seed dataset to *tmp_path* with the given quote pair.

    Returns the dataset name (the directory name relative to seeds/).
    Tests monkeypatch ``_SEEDS_ROOT`` so the loader picks up ``tmp_path``.
    """
    dataset_name = "quote-integrity-test"
    dataset_dir = tmp_path / dataset_name
    dataset_dir.mkdir()

    _ = (dataset_dir / "jurisdiction.yaml").write_text(
        yaml.dump(
            [
                {
                    "slug": "qi-city",
                    "name": "QI City",
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
                    "jurisdiction": "qi-city",
                    "url": "https://qi.example.com/recycling",
                    "title": "QI City Recycling",
                    "authority_level": 1,
                    "source_text": source_text,
                }
            ]
        ),
        encoding="utf-8",
    )

    _ = (dataset_dir / "materials.yaml").write_text(
        yaml.dump(
            [
                {
                    "slug": "qi-cans",
                    "canonical_name": "QI Aluminum Can",
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
                    "slug": "qi-city-qi-cans",
                    "jurisdiction": "qi-city",
                    "material": "qi-cans",
                    "source_document": "https://qi.example.com/recycling",
                    "disposition": "curbside_recycle",
                    "accepted_status": "accepted",
                    "source_quote": source_quote,
                    "confidence": "high",
                }
            ]
        ),
        encoding="utf-8",
    )

    return dataset_name


@pytest.mark.integration
def test_curly_quote_in_fixture_loads_successfully(
    db_engine: Engine,
    clean_db: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """Curly-quoted source_quote loads when normalized text matches."""
    _ = clean_db  # injected for DB truncation side effect
    import src.cli.seed as seed_module  # noqa: PLC0415

    monkeypatch.setattr(seed_module, "_SEEDS_ROOT", tmp_path)

    # Source has straight double quotes around "curbside recycling".
    source_text = 'Aluminum cans are accepted for "curbside recycling".'
    # Fixture uses curly double quotes around the same span (U+201C, U+201D).
    # The normalizer straightens them so the substring check passes.
    source_quote = _LQUOTE + "curbside recycling" + _RQUOTE

    dataset = _make_dataset(tmp_path, source_text, source_quote)

    from sqlalchemy.orm import Session  # noqa: PLC0415

    from src.cli.seed import run_seed  # noqa: PLC0415

    # Should not raise.
    with Session(db_engine) as session, session.begin():
        run_seed(dataset, session)


@pytest.mark.integration
def test_substring_mismatch_raises_seed_integrity_error(
    db_engine: Engine,
    clean_db: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """Mismatched source_quote raises SeedIntegrityError before any DB write."""
    _ = clean_db  # injected for DB truncation side effect
    import src.cli.seed as seed_module  # noqa: PLC0415

    monkeypatch.setattr(seed_module, "_SEEDS_ROOT", tmp_path)

    source_text = "Aluminum cans are accepted for curbside recycling."
    source_quote = "Styrofoam is definitely not accepted anywhere ever."

    dataset = _make_dataset(tmp_path, source_text, source_quote)

    from sqlalchemy import text  # noqa: PLC0415
    from sqlalchemy.orm import Session  # noqa: PLC0415

    from src.cli.seed import run_seed  # noqa: PLC0415

    with (
        pytest.raises(SeedIntegrityError) as exc_info,
        Session(db_engine) as session,
        session.begin(),
    ):
        run_seed(dataset, session)

    assert "qi-city-qi-cans" in str(exc_info.value)

    # Confirm no rows were written in any table.
    _jur_sql = "SELECT count(*) FROM jurisdictions WHERE slug = 'qi-city'"
    _mat_sql = "SELECT count(*) FROM materials WHERE slug = 'qi-cans'"
    _src_sql = (
        "SELECT count(*) FROM source_documents"
        " WHERE url = 'https://qi.example.com/recycling'"
    )
    with Session(db_engine) as session:
        jur_count = cast(int, session.execute(text(_jur_sql)).scalar())
        mat_count = cast(int, session.execute(text(_mat_sql)).scalar())
        src_count = cast(int, session.execute(text(_src_sql)).scalar())

    assert jur_count == 0, (
        "Jurisdiction row was written despite integrity failure"
    )
    assert mat_count == 0, "Materials row was written despite integrity failure"
    assert src_count == 0, (
        "source_documents row was written despite integrity failure"
    )
