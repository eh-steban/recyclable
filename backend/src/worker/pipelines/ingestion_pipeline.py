"""Ingestion pipeline -- wires concrete implementations into IngestSource.

Runs in the worker process, never in the FastAPI HTTP handler (INV-OPS-001).

Two-transaction shape (repositories.md Principle 9):

  Transaction 1: save the IngestionRunTrace and commit.
  No transaction: network fetch + Opus extraction (up to 120 s).
  Transaction 2: save the IngestionReport and commit.

This ensures Postgres is not holding an open transaction during the
potentially long network + LLM calls.
"""

import logging

from sqlalchemy.orm import Session

from src.application.ingest_source import IngestSource
from src.application.ingest_source_command import IngestSourceCommand
from src.config import settings
from src.domain.ingestion.ingestion_report import IngestionReportId
from src.infra.db.repos.ingestion_report_repo import PgIngestionReportRepo
from src.infra.db.repos.ingestion_run_trace_repo import PgIngestionRunTraceRepo
from src.infra.db.session import get_engine
from src.infra.external.anthropic_client import OpusIngestionClient
from src.infra.external.source_fetcher import HttpSourceFetcher

logger = logging.getLogger(__name__)


def run_ingestion(command: IngestSourceCommand) -> IngestionReportId:
    """Wire concrete implementations and run IngestSource.

    Opens a new session and drives the two-transaction pipeline shape:
    trace commit, then fetch+extract (no open tx), then report commit.
    The caller (cli/ingest.py) is responsible for reporting the result.
    """
    engine = get_engine()
    with Session(engine) as session:
        report_repo = PgIngestionReportRepo(session)
        trace_repo = PgIngestionRunTraceRepo(session)
        fetcher = HttpSourceFetcher()
        llm = OpusIngestionClient(api_key=settings.anthropic_api_key)

        service = IngestSource(
            report_repo=report_repo,
            trace_repo=trace_repo,
            fetcher=fetcher,
            llm=llm,
        )

        try:
            with session.begin():
                trace_id = service.run_trace_phase(command)
        except Exception:
            logger.exception(
                "ingestion pipeline failed (trace phase): seed_url=%r",
                command.seed_url,
            )
            raise

        try:
            source, candidates = service.run_extract_phase(command, trace_id)
        except Exception:
            logger.exception(
                "ingestion pipeline failed (extract phase): seed_url=%r",
                command.seed_url,
            )
            raise

        try:
            with session.begin():
                report_id = service.run_report_phase(
                    command, trace_id, source, candidates
                )
        except Exception:
            logger.exception(
                "ingestion pipeline failed (report phase): seed_url=%r",
                command.seed_url,
            )
            raise

        logger.info(
            "ingestion pipeline complete: report_id=%s seed_url=%r",
            report_id,
            command.seed_url,
        )
        return report_id
