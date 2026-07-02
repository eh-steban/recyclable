"""Ingest CLI -- fetch a source URL and extract candidate recycling rules.

Usage::

    python -m src.cli ingest --source <url> --jurisdiction-id <uuid>

Fetches one page (SSRF-safe), makes a single Opus call to extract candidate
rules with confidence + provenance, and persists a pending_review
IngestionReport. Prints the report ID on success.

The pipeline runs in this process (worker mode) and is not part of the
FastAPI HTTP surface (INV-OPS-001).
"""

# pyright: reportAny=false, reportExplicitAny=false

import argparse
import logging
import sys
import uuid
from typing import cast

from src.application.ingest_source_command import IngestSourceCommand
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.worker.pipelines.ingestion_pipeline import run_ingestion


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
        "--jurisdiction-id",
        required=True,
        metavar="UUID",
        help="UUID of the jurisdiction this run targets.",
    )
    _ = parser.add_argument(
        "--jurisdiction-name",
        required=True,
        metavar="NAME",
        help=(
            "Human-readable display name of the jurisdiction"
            " (e.g. 'Denver, CO'). Used in the extraction prompt"
            " (INV-LLM-008)."
        ),
    )
    _ = parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable DEBUG logging.",
    )
    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    source_url: str = cast(str, args.source)
    jurisdiction_id_str: str = cast(str, args.jurisdiction_id)
    jurisdiction_name: str = cast(str, args.jurisdiction_name)

    try:
        jurisdiction_uuid = uuid.UUID(jurisdiction_id_str)
    except ValueError:
        msg = (
            f"Error: --jurisdiction-id {jurisdiction_id_str!r}"
            " is not a valid UUID."
        )
        print(msg, file=sys.stderr)
        sys.exit(1)

    command = IngestSourceCommand(
        seed_url=source_url,
        jurisdiction_id=JurisdictionId(jurisdiction_uuid),
        jurisdiction_name=jurisdiction_name,
    )

    try:
        report_id = run_ingestion(command)
    except Exception as exc:
        print(f"Error: ingestion failed -- {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Ingestion complete. Report ID: {report_id}")


if __name__ == "__main__":
    main()
