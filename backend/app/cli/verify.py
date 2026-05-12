"""Verifier CLI -- read-only data-integrity and acceptance-query checks.

Usage::

    python -m app.cli verify --dataset denver-easy

The verifier runs three classes of checks:

1. **Fixture re-parse** -- loads YAML fixtures through the same Pydantic
   models the seed loader uses.  Catches fixture regressions without
   touching the DB.

2. **Quote integrity** -- re-runs the normalized-substring check against
   the current DB state (reads ``source_documents.source_text`` from the
   DB, compares against the fixture ``source_quote`` values).

3. **Acceptance queries** -- executes the six SQL queries from the spec's
   *Acceptance queries* section and validates the result against expected
   ranges.

Exits 0 iff all checks pass; exits 1 otherwise with a per-check summary.
No writes are performed.
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import pathlib
import sys
from typing import cast

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.cli._seed_parse import (
    RuleRow,
    SourceDocumentRow,
    as_list_of_dicts,
    as_list_of_rows,
    load_yaml,
    parse_jurisdictions,
    parse_materials,
    parse_regression_cases,
    parse_rules,
    parse_source_documents,
    validate_dataset_path,
)
from app.domain.exceptions import EntityNotFoundError, SeedSchemaError
from app.domain.quote_normalize import normalize
from app.infra.db.session import get_engine

logger = logging.getLogger(__name__)

# __file__ = backend/app/cli/verify.py; parents[2] = backend/
_SEEDS_ROOT = pathlib.Path(__file__).parents[2] / "seeds"

# ---- Expected ranges for acceptance queries ----
# Each entry: (check_name, sql, min_inclusive, max_inclusive | None)
_ACCEPTANCE_CHECKS: list[tuple[str, str, int, int | None]] = [
    (
        "table-count (expect 7)",
        """
        SELECT count(*) FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN (
            'jurisdictions', 'materials', 'material_aliases',
            'source_documents', 'rules', 'regression_cases',
            'answer_audit_records'
          )
        """,
        7,
        7,
    ),
    (
        "denver jurisdiction (expect 1)",
        """
        SELECT count(*) FROM jurisdictions
        WHERE slug = 'denver'
          AND supported_status = 'supported'
        """,
        1,
        1,
    ),
    (
        "source documents with authority_level <= 2 (expect >= 2)",
        """
        SELECT count(*) FROM source_documents
        WHERE jurisdiction_id = (
            SELECT id FROM jurisdictions WHERE slug = 'denver'
          )
          AND authority_level <= 2
          AND length(source_text) > 0
        """,
        2,
        None,  # no upper bound
    ),
    (
        "active rules with full citation (expect 5-8)",
        """
        SELECT count(*) FROM rules
        WHERE jurisdiction_id = (
            SELECT id FROM jurisdictions WHERE slug = 'denver'
          )
          AND superseded_by IS NULL
          AND source_document_id IS NOT NULL
          AND length(source_quote) > 0
        """,
        5,
        8,
    ),
    (
        "regression case count (expect 8)",
        """
        SELECT count(*) FROM regression_cases
        WHERE expected_status IS NOT NULL
          AND expected_disposition IS NOT NULL
        """,
        8,
        8,
    ),
]


def _check_fixture_parse(dataset: str) -> list[str]:
    """Re-parse fixtures through Pydantic models.

    Returns a list of failure messages (empty = all pass).
    Does not write to the DB.
    """
    failures: list[str] = []
    dataset_dir = validate_dataset_path(dataset, _SEEDS_ROOT)

    jur_data = load_yaml(dataset_dir / "jurisdiction.yaml")
    src_data = load_yaml(dataset_dir / "source_documents.yaml")
    mat_data = load_yaml(dataset_dir / "materials.yaml")
    rule_data = load_yaml(dataset_dir / "rules.yaml")
    rc_data = load_yaml(dataset_dir / "regression_cases.yaml")

    # Parse jurisdictions first -- needed for downstream maps.
    try:
        jurisdictions = parse_jurisdictions(jur_data or [], dataset)
        jurisdiction_map = {j.slug: j for j in jurisdictions}
    except (SeedSchemaError, EntityNotFoundError) as exc:
        failures.append(f"fixture-parse jurisdiction.yaml: {exc}")
        return failures  # can't continue without jurisdictions

    try:
        source_docs = parse_source_documents(
            src_data or [], dataset, jurisdiction_map
        )
        source_doc_map = {doc.url: doc for doc in source_docs}
    except (SeedSchemaError, EntityNotFoundError) as exc:
        failures.append(f"fixture-parse source_documents.yaml: {exc}")
        source_doc_map = {}

    try:
        material_tuples = parse_materials(mat_data or [], dataset)
        material_map = {m.slug: m for (m, _) in material_tuples}
    except (SeedSchemaError, EntityNotFoundError) as exc:
        failures.append(f"fixture-parse materials.yaml: {exc}")
        material_map = {}

    try:
        _ = parse_rules(
            rule_data or [],
            dataset,
            jurisdiction_map,
            material_map,
            source_doc_map,
        )
    except (SeedSchemaError, EntityNotFoundError) as exc:
        failures.append(f"fixture-parse rules.yaml: {exc}")

    if rc_data is not None:
        try:
            _ = parse_regression_cases(
                rc_data, dataset, jurisdiction_map, material_map
            )
        except (SeedSchemaError, EntityNotFoundError) as exc:
            failures.append(f"fixture-parse regression_cases.yaml: {exc}")

    return failures


def _check_quote_integrity(dataset: str, session: Session) -> list[str]:
    """Re-run quote-integrity checks against live DB source_text.

    Reads ``source_documents`` from the DB and checks each fixture rule's
    ``source_quote`` against the stored text.  No writes performed.

    Returns a list of failure messages.
    """
    failures: list[str] = []
    dataset_dir = validate_dataset_path(dataset, _SEEDS_ROOT)
    rule_data = load_yaml(dataset_dir / "rules.yaml")
    src_data = load_yaml(dataset_dir / "source_documents.yaml")

    if rule_data is None or src_data is None:
        return failures  # nothing to check

    # Build url -> DB source_text map (URL is the unique stable key).
    url_to_db_text: dict[str, str] = {}
    src_items: list[SourceDocumentRow] = []
    with contextlib.suppress(SeedSchemaError):
        src_items = as_list_of_rows(
            src_data, f"{dataset}/source_documents.yaml", SourceDocumentRow
        )
    for src_item in src_items:
        url: str = src_item.get("url", "")
        db_row = session.execute(
            text("SELECT source_text FROM source_documents WHERE url = :url"),
            {"url": url},
        ).fetchone()
        if db_row is not None:
            url_to_db_text[url] = cast(str, db_row[0])

    rule_items: list[RuleRow] = []
    with contextlib.suppress(SeedSchemaError):
        rule_items = as_list_of_dicts(rule_data, f"{dataset}/rules.yaml")
    for i, item in enumerate(rule_items):
        rule_slug: str = item.get("slug", f"rule[{i}]")
        source_doc_url: str = item.get("source_document", "")
        source_quote: str = item.get("source_quote", "")

        if source_doc_url not in url_to_db_text:
            # Source document not in DB -- seed hasn't run yet (acceptable
            # during fixture-only check, flagged separately).
            continue

        db_text = url_to_db_text[source_doc_url]
        if normalize(source_quote) not in normalize(db_text):
            excerpt = source_quote[:60]
            failures.append(
                f"quote-integrity rule='{rule_slug}':"
                + " normalized quote not found in DB source_text."
                + f" Quote excerpt: '{excerpt}...'"
            )

    return failures


def _check_acceptance_queries(
    session: Session,
) -> list[tuple[str, bool, str]]:
    """Run all acceptance queries.

    Returns a list of (check_name, passed, detail) tuples.
    """
    results: list[tuple[str, bool, str]] = []
    for name, sql, min_val, max_val in _ACCEPTANCE_CHECKS:
        row = session.execute(text(sql.strip())).fetchone()
        count: int = cast(int, row[0]) if row else 0
        passed = count >= min_val and (max_val is None or count <= max_val)
        if max_val is None:
            detail = f"count={count} (expected >= {min_val})"
        else:
            detail = f"count={count} (expected {min_val}-{max_val})"
        results.append((name, passed, detail))

    # Sixth check -- regression case category distribution.
    # Spec requires exactly 8 cases with these per-category ranges:
    #   accepted:         2-3   (expected_status='accepted',
    #                            refusal_required=false)
    #   rejected:         2     (expected_status='rejected',
    #                            refusal_required=false)
    #   conditional:      1-2   (expected_status='conditional',
    #                            refusal_required=false)
    #   refusal_required: 1-2   (refusal_required=true, any expected_status)
    dist_sql = """
        SELECT
            count(*) FILTER (
                WHERE expected_status = 'accepted' AND NOT refusal_required
            ) AS accepted,
            count(*) FILTER (
                WHERE expected_status = 'rejected' AND NOT refusal_required
            ) AS rejected,
            count(*) FILTER (
                WHERE expected_status = 'conditional' AND NOT refusal_required
            ) AS conditional,
            count(*) FILTER (WHERE refusal_required) AS refusal_required,
            count(*) AS total
        FROM regression_cases
        WHERE expected_status IS NOT NULL
          AND expected_disposition IS NOT NULL
    """
    row = session.execute(text(dist_sql.strip())).fetchone()
    accepted = cast(int, row[0]) if row else 0
    rejected = cast(int, row[1]) if row else 0
    conditional = cast(int, row[2]) if row else 0
    refusal_req = cast(int, row[3]) if row else 0
    total = cast(int, row[4]) if row else 0

    dist_failures: list[str] = []
    if total != 8:
        dist_failures.append(f"total={total} (expected 8)")
    if not (2 <= accepted <= 3):
        dist_failures.append(f"accepted={accepted} (expected 2-3)")
    if rejected != 2:
        dist_failures.append(f"rejected={rejected} (expected 2)")
    if not (1 <= conditional <= 2):
        dist_failures.append(f"conditional={conditional} (expected 1-2)")
    if not (1 <= refusal_req <= 2):
        dist_failures.append(f"refusal_required={refusal_req} (expected 1-2)")

    dist_passed = len(dist_failures) == 0
    dist_detail = (
        f"total={total}, accepted={accepted}, rejected={rejected}, "
        f"conditional={conditional}, refusal_required={refusal_req}"
    )
    if dist_failures:
        dist_detail += " -- FAILED: " + "; ".join(dist_failures)
    results.append(("regression-case distribution", dist_passed, dist_detail))
    return results


def run_verify(dataset: str, session: Session) -> bool:
    """Execute all verification checks.  Returns True iff all pass.

    Args:
        dataset: Name of the seed dataset (used for fixture re-parse and
            quote-integrity checks).
        session: Open read-only SQLAlchemy session.
    """
    all_passed = True
    check_lines: list[str] = []

    # 1. Fixture re-parse.
    fixture_failures = _check_fixture_parse(dataset)
    for msg in fixture_failures:
        check_lines.append(f"  FAIL  {msg}")
        all_passed = False
    if not fixture_failures:
        check_lines.append("  PASS  fixture parse")

    # 2. Quote integrity (requires DB).
    qi_failures = _check_quote_integrity(dataset, session)
    for msg in qi_failures:
        check_lines.append(f"  FAIL  {msg}")
        all_passed = False
    if not qi_failures:
        check_lines.append("  PASS  quote integrity (DB)")

    # 3. Acceptance queries.
    for name, passed, detail in _check_acceptance_queries(session):
        status = "PASS" if passed else "FAIL"
        check_lines.append(f"  {status}  {name}: {detail}")
        if not passed:
            all_passed = False

    summary = "PASSED" if all_passed else "FAILED"
    print(f"\nVerification {summary} for dataset '{dataset}':\n")
    for line in check_lines:
        print(line)
    print()

    return all_passed


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for the verifier."""
    parser = argparse.ArgumentParser(
        prog="python -m app.cli verify",
        description=(
            "Re-parse fixtures and run acceptance queries against Postgres. "
            "No DB writes are performed. Exits 0 iff all checks pass."
        ),
    )
    _ = parser.add_argument(
        "--dataset",
        required=True,
        metavar="NAME",
        help=(
            "Name of the seed dataset to verify"
            " (subdirectory of backend/seeds/)."
        ),
    )
    args = parser.parse_args(argv)
    dataset: str = cast(str, args.dataset)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    engine = get_engine()
    with Session(engine) as session:
        passed = run_verify(dataset, session)

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
