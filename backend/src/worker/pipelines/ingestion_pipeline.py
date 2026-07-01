"""Ingestion pipeline -- wires concrete implementations into IngestSource.

Runs in the worker process, never in the FastAPI HTTP handler (INV-OPS-001).
Constructs the dependency graph from config + DB session and delegates to the
IngestSource application service.

Story 1: single-URL, single-shot Opus call. Stories 3+ extend to a bounded
agentic loop without changing this module's interface.
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

    Opens a new session, commits on success, rolls back on any exception.
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
                report_id = service.run(command)
        except Exception:
            logger.exception(
                "ingestion pipeline failed: seed_url=%r", command.seed_url
            )
            raise

        logger.info(
            "ingestion pipeline complete: report_id=%s seed_url=%r",
            report_id,
            command.seed_url,
        )
        return report_id
