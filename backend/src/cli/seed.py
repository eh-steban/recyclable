"""Seed loader CLI -- load YAML fixture datasets into Postgres.

Usage::

    python -m app.cli seed --dataset denver-easy

The ``--dataset`` argument resolves to ``backend/seeds/<dataset>/``.
All YAML files are loaded into Pydantic domain models (schema errors
surface before any DB write), quote integrity is validated, and then
all rows are upserted inside a single transaction.

Upsert semantics:

- ``jurisdictions``    -- ``ON CONFLICT (slug) DO UPDATE``
- ``materials``        -- ``ON CONFLICT (slug) DO UPDATE``
- ``material_aliases`` -- ``ON CONFLICT (material_id, alias) DO NOTHING``
- ``source_documents`` -- ``ON CONFLICT (id) DO UPDATE``
- ``rules``            -- conflict on partial unique index (active rules)
- ``regression_cases`` -- ``ON CONFLICT (id) DO UPDATE``

Source document reference style:
YAML files reference source documents by their ``url`` field (the unique
stable key). Use ``source_document: <url>`` in ``rules.yaml`` and other
cross-reference sites. Titles are display-only and must not be used as
lookup keys.
"""

import argparse
import logging
import pathlib
import sys
from typing import cast

from sqlalchemy.orm import Session

from src.cli._seed_parse import (
    load_yaml,
    parse_jurisdictions,
    parse_materials,
    parse_regression_cases,
    parse_rules,
    parse_source_documents,
    validate_dataset_path,
)
from src.domain.audit.regression_case import RegressionCase
from src.domain.exceptions import (
    EntityNotFoundError,
    SeedIntegrityError,
    SeedSchemaError,
)
from src.domain.knowledge_base.material import MaterialAlias
from src.infra.db.repos.jurisdiction_repo import (
    SqlJurisdictionRepo,
)
from src.infra.db.repos.material_repo import SqlMaterialRepo
from src.infra.db.repos.regression_case_repo import (
    SqlRegressionCaseRepo,
)
from src.infra.db.repos.rule_repo import SqlRuleRepo
from src.infra.db.repos.source_document_repo import (
    SqlSourceDocumentRepo,
)
from src.infra.db.session import get_engine

logger = logging.getLogger(__name__)

# Seeds are stored at backend/seeds/ -- two levels above the cli package.
# __file__ = backend/app/cli/seed.py
# parents[2] = backend/
_SEEDS_ROOT = pathlib.Path(__file__).parents[2] / "seeds"


def _require_dataset_dir(dataset: str) -> pathlib.Path:
    """Return the dataset directory, raising SystemExit with a clear message
    if it does not exist or contains no YAML files."""
    dataset_dir = validate_dataset_path(dataset, _SEEDS_ROOT)
    if not dataset_dir.is_dir():
        logger.error(
            "seed dataset not found: dataset=%s expected_path=%s",
            dataset,
            dataset_dir,
        )
        print(
            f"Error: seed dataset '{dataset}' not found.\n"
            + f"Expected directory: {dataset_dir}\n"
            + "Run 'ls backend/seeds/' to see available datasets.",
            file=sys.stderr,
        )
        sys.exit(1)

    yaml_files = list(dataset_dir.glob("*.yaml")) + list(
        dataset_dir.glob("*.yml")
    )
    if not yaml_files:
        logger.error(
            "seed dataset directory is empty: dataset=%s path=%s",
            dataset,
            dataset_dir,
        )
        print(
            f"Error: seed dataset '{dataset}' directory exists "
            + f"but contains no YAML files.\nPath: {dataset_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    return dataset_dir


def run_seed(dataset: str, session: Session) -> None:
    """Execute the full seed load for *dataset* inside *session*.

    The caller is responsible for committing or rolling back the session.
    This function raises on any schema mismatch or integrity violation
    before touching the database.

    Args:
        dataset: Name of the dataset subdirectory under ``seeds/``.
        session: An open SQLAlchemy session (not yet committed).
    """
    dataset_dir = _require_dataset_dir(dataset)
    logger.info("seed: loading dataset=%s path=%s", dataset, dataset_dir)

    # ---- 1. Load YAML files (fail fast on missing required files) ----
    jur_data = load_yaml(dataset_dir / "jurisdiction.yaml")
    src_data = load_yaml(dataset_dir / "source_documents.yaml")
    mat_data = load_yaml(dataset_dir / "materials.yaml")
    rule_data = load_yaml(dataset_dir / "rules.yaml")
    rc_data = load_yaml(dataset_dir / "regression_cases.yaml")

    if jur_data is None:
        raise SeedSchemaError(
            f"missing required file: {dataset}/jurisdiction.yaml"
        )
    if src_data is None:
        raise SeedSchemaError(
            f"missing required file: {dataset}/source_documents.yaml"
        )
    if mat_data is None:
        raise SeedSchemaError(
            f"missing required file: {dataset}/materials.yaml"
        )
    if rule_data is None:
        raise SeedSchemaError(f"missing required file: {dataset}/rules.yaml")
    # regression_cases.yaml is optional -- not all datasets have eval cases.

    # ---- 2. Parse into domain models (all validation before DB) ----
    logger.debug("seed: parsing jurisdictions")
    jurisdictions = parse_jurisdictions(jur_data, dataset)
    jurisdiction_map = {j.slug: j for j in jurisdictions}

    logger.debug("seed: parsing source_documents")
    source_docs = parse_source_documents(src_data, dataset, jurisdiction_map)
    # Source docs are keyed by URL (the unique stable key).
    # YAML rule entries must reference source documents via their ``url`` field.
    source_doc_map = {doc.url: doc for doc in source_docs}

    logger.debug("seed: parsing materials")
    material_tuples = parse_materials(mat_data, dataset)
    material_map = {m.slug: m for (m, _) in material_tuples}

    logger.debug("seed: parsing rules (including quote-integrity check)")
    rules = parse_rules(
        rule_data, dataset, jurisdiction_map, material_map, source_doc_map
    )

    regression_cases: list[RegressionCase] = []
    if rc_data is not None:
        logger.debug("seed: parsing regression_cases")
        regression_cases = parse_regression_cases(
            rc_data, dataset, jurisdiction_map, material_map
        )

    # ---- 3. Write to DB (all inside the caller's transaction) ----
    jur_repo = SqlJurisdictionRepo(session)
    mat_repo = SqlMaterialRepo(session)
    src_repo = SqlSourceDocumentRepo(session)
    rule_repo = SqlRuleRepo(session)
    rc_repo = SqlRegressionCaseRepo(session)

    logger.info("seed: writing %d jurisdiction(s)", len(jurisdictions))
    for j in jurisdictions:
        jur_repo.save(j)

    logger.info("seed: writing %d source document(s)", len(source_docs))
    for doc in source_docs:
        src_repo.save(doc)

    logger.info(
        "seed: writing %d material(s) (plus aliases)", len(material_tuples)
    )
    for material, aliases in material_tuples:
        mat_repo.save(material)
        for alias_text in aliases:
            alias = MaterialAlias(material_id=material.id, alias=alias_text)
            mat_repo.save_alias(alias)

    logger.info("seed: writing %d rule(s)", len(rules))
    for rule in rules:
        rule_repo.save(rule)

    if regression_cases:
        logger.info(
            "seed: writing %d regression case(s)", len(regression_cases)
        )
        for case in regression_cases:
            rc_repo.save(case)

    _fmt = (
        "seed: dataset=%s complete -- %d jurisdictions,"
        " %d source_docs, %d materials, %d rules, %d regression_cases"
    )
    logger.info(
        _fmt,
        dataset,
        len(jurisdictions),
        len(source_docs),
        len(material_tuples),
        len(rules),
        len(regression_cases),
    )


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for the seed loader."""
    parser = argparse.ArgumentParser(
        prog="python -m app.cli seed",
        description="Load a YAML seed dataset into Postgres.",
    )
    _ = parser.add_argument(
        "--dataset",
        required=True,
        metavar="NAME",
        help="Name of the seed dataset (subdirectory of backend/seeds/).",
    )
    args = parser.parse_args(argv)
    dataset: str = cast(str, args.dataset)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    engine = get_engine()
    _seed_error: Exception | None = None
    with Session(engine) as session:
        try:
            with session.begin():
                run_seed(dataset, session)
        except (
            SeedSchemaError,
            SeedIntegrityError,
            EntityNotFoundError,
        ) as exc:
            logger.error("seed failed: %s", exc)
            print(f"Error: {exc}", file=sys.stderr)
            _seed_error = exc

    if _seed_error is not None:
        sys.exit(1)
    print(f"Seed dataset '{dataset}' loaded successfully.")


if __name__ == "__main__":
    main()
