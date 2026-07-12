"""Ingest CLI -- fetch a source URL and extract candidate recycling rules.

Usage::

    python -m src.cli ingest --source <url> --jurisdiction <name>

Resolves the jurisdiction from a case-insensitive name fragment (e.g.
"denver" -> "City and County of Denver"), fetches one page (SSRF-safe),
makes a single Opus call to extract candidate rules with confidence +
provenance, and persists a pending_review IngestionReport. Prints the
report ID on success.

The pipeline runs in this process (worker mode) and is not part of the
FastAPI HTTP surface (INV-OPS-001).
"""

import argparse
import logging
import sys
from typing import cast

from sqlalchemy.orm import Session

from src.application.ingest_source_command import IngestSourceCommand
from src.domain.knowledge_base.jurisdiction import Jurisdiction
from src.domain.knowledge_base.jurisdiction_repo import JurisdictionRepo
from src.infra.db.repos.jurisdiction_repo import PgJurisdictionRepo
from src.infra.db.session import get_engine
from src.worker.pipelines.ingestion_pipeline import run_ingestion


def _select_jurisdiction(repo: JurisdictionRepo, query: str) -> Jurisdiction:
    """Return the single jurisdiction matching *query*, else exit(1).

    The operator passes a name fragment; the canonical DB name is what
    reaches the extraction prompt (INV-LLM-008), never the raw query. On
    zero or multiple matches, list the candidates and exit nonzero so the
    operator can rerun with a precise fragment.
    """
    matches = repo.search_by_name(query)
    if len(matches) == 1:
        return matches[0]

    # An empty query matches every row: use it to show what IS available
    # when the operator's fragment matched nothing.
    available = matches or repo.search_by_name("")
    if matches:
        header = f"Error: {query!r} matches {len(matches)} jurisdictions:"
    elif available:
        header = f"Error: no jurisdiction matches {query!r}. Available:"
    else:
        print(
            "Error: no jurisdictions found. Seed one first, e.g."
            + " python -m src.cli seed --dataset denver-easy",
            file=sys.stderr,
        )
        sys.exit(1)
    print(header, file=sys.stderr)
    for jurisdiction in available:
        print(f"  {jurisdiction.name}  ({jurisdiction.slug})", file=sys.stderr)
    sys.exit(1)


def _resolve_jurisdiction(query: str) -> Jurisdiction:
    with Session(get_engine()) as session:
        return _select_jurisdiction(PgJurisdictionRepo(session), query)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for the ingest command."""
    parser = argparse.ArgumentParser(
        prog="python -m src.cli ingest",
        description=(
            "Fetch a source URL and extract candidate recycling rules."
        ),
    )
    _ = parser.add_argument(
        "--source",
        required=True,
        metavar="URL",
        help="Authoritative HTTPS URL of the source page to ingest.",
    )
    _ = parser.add_argument(
        "--jurisdiction",
        required=True,
        metavar="NAME",
        help=(
            "Jurisdiction name or fragment (case-insensitive), e.g."
            " 'denver'. Resolved against seeded jurisdictions."
        ),
    )
    _ = parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable DEBUG logging.",
    )
    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO  # pyright: ignore[reportAny]
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    source_url: str = cast(str, args.source)
    jurisdiction_query: str = cast(str, args.jurisdiction)

    jurisdiction = _resolve_jurisdiction(jurisdiction_query)

    command = IngestSourceCommand(
        seed_url=source_url,
        jurisdiction_id=jurisdiction.id,
        jurisdiction_name=jurisdiction.name,
    )

    try:
        report_id = run_ingestion(command)
    except Exception as exc:
        print(f"Error: ingestion failed -- {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Ingestion complete. Report ID: {report_id}")


if __name__ == "__main__":
    main()
