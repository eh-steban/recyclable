"""IngestSource application service -- ingestion worker task coordinator.

Pipeline (two-transaction shape, repositories.md Principle 9):

  Transaction 1  -- run_trace_phase():
      Mint and persist IngestionRunTrace; commit.

  No transaction -- run_extract_phase():
      Fetch the seed URL; call IngestionLLM.extract().
      Network I/O and a potentially 120 s Opus call run with no open
      Postgres transaction.

  Transaction 2  -- run_report_phase():
      Assemble IngestionReport; transition to pending_review (Validator);
      persist; commit.

The caller (ingestion_pipeline.py) wraps each phase in its own
session.begin() block. The service itself is transaction-agnostic and
imports domain ports only (DDD inward-dependency rule).
"""

import logging
from datetime import UTC, datetime
from typing import final

from src.application.ingest_source_command import IngestSourceCommand
from src.domain.ingestion.candidate_rule import CandidateRule
from src.domain.ingestion.ingestion_llm import OPUS_MODEL_ID, IngestionLLM
from src.domain.ingestion.ingestion_report import (
    IngestionReport,
    IngestionReportId,
    IngestionReportStatus,
    ProposedRuleChange,
    RuleOp,
)
from src.domain.ingestion.ingestion_report_repo import IngestionReportRepo
from src.domain.ingestion.ingestion_run_trace import (
    IngestionRunTrace,
    IngestionRunTraceId,
)
from src.domain.ingestion.ingestion_run_trace_repo import IngestionRunTraceRepo
from src.domain.ingestion.source_fetcher import SourceFetcher, SourceFetchResult
from src.llm.prompts.extract_rules import (
    EXTRACT_RULES_PROMPT_NAME,
    EXTRACT_RULES_VERSION,
)

logger = logging.getLogger(__name__)


def _candidate_to_change(candidate: CandidateRule) -> ProposedRuleChange:
    """Map a CandidateRule to a ProposedRuleChange with op=add."""
    rule: dict[str, object] = {
        "jurisdiction_id": str(candidate.jurisdiction_id),
        "material_slug": candidate.material_slug,
        "disposition": candidate.disposition,
        "accepted_status": candidate.accepted_status,
        "preparation_steps": list(candidate.preparation_steps),
        "exceptions": list(candidate.exceptions),
        "warnings": list(candidate.warnings),
        "effective_from": candidate.effective_from,
    }
    return ProposedRuleChange(
        op=RuleOp.ADD,
        rule=rule,
        confidence=candidate.confidence,
        source_document_id=candidate.source_document_id,
        source_quote=candidate.source_quote,
    )


@final
class IngestSource:
    """Application service for the ingestion worker pipeline.

    Constructor parameters are domain ports; the worker pipeline injects
    concrete implementations at call time.

    Use the three-phase methods for the two-transaction shape:
        trace_id = svc.run_trace_phase(cmd)          # tx 1
        source, candidates = svc.run_extract_phase(cmd, trace_id)  # no tx
        report_id = svc.run_report_phase(...)         # tx 2
    """

    def __init__(
        self,
        report_repo: IngestionReportRepo,
        trace_repo: IngestionRunTraceRepo,
        fetcher: SourceFetcher,
        llm: IngestionLLM,
    ) -> None:
        self._report_repo = report_repo
        self._trace_repo = trace_repo
        self._fetcher = fetcher
        self._llm = llm

    def run_trace_phase(
        self, command: IngestSourceCommand
    ) -> IngestionRunTraceId:
        """Mint and persist the IngestionRunTrace (transaction 1).

        The caller commits the session after this returns.
        """
        now = datetime.now(tz=UTC)
        trace_id = self._trace_repo.next_identity()
        trace = IngestionRunTrace(
            id=trace_id,
            seed_url=command.seed_url,
            created_at=now,
        )
        self._trace_repo.save(trace)
        logger.info(
            "ingestion trace minted: trace_id=%s seed_url=%r",
            trace_id,
            command.seed_url,
        )
        return trace_id

    def run_extract_phase(
        self,
        command: IngestSourceCommand,
        trace_id: IngestionRunTraceId,
    ) -> tuple[SourceFetchResult, list[CandidateRule]]:
        """Fetch the source URL and call the LLM (no open transaction).

        Network I/O and Opus extraction run here, outside any DB transaction.
        Returns the fetched source and extracted candidates.
        """
        source = self._fetcher.fetch(command.seed_url, authority_level=3)
        logger.info(
            "source fetched: trace_id=%s url=%r content_type=%r",
            trace_id,
            source.url,
            source.content_type,
        )

        candidates: list[CandidateRule] = self._llm.extract(
            source=source,
            jurisdiction_id=str(command.jurisdiction_id.value),
            jurisdiction_name=command.jurisdiction_name,
            prompt_name=EXTRACT_RULES_PROMPT_NAME,
            prompt_version=EXTRACT_RULES_VERSION,
        )
        logger.info(
            "extraction complete: trace_id=%s candidate_count=%d",
            trace_id,
            len(candidates),
        )
        return source, candidates

    def run_report_phase(
        self,
        command: IngestSourceCommand,
        trace_id: IngestionRunTraceId,
        source: SourceFetchResult,
        candidates: list[CandidateRule],
    ) -> IngestionReportId:
        """Assemble, validate, and persist the IngestionReport (transaction 2).

        The caller commits the session after this returns.
        Returns the IngestionReportId of the persisted pending_review report.
        """
        now = datetime.now(tz=UTC)
        proposed_changes = tuple(_candidate_to_change(c) for c in candidates)
        report_id = self._report_repo.next_identity()
        draft = IngestionReport(
            id=report_id,
            jurisdiction_id=command.jurisdiction_id,
            trace_id=trace_id.value,
            seed_url=source.url,
            proposed_rule_changes=proposed_changes,
            conflicts=(),
            missing_fields=(),
            status=IngestionReportStatus.DRAFT,
            created_at=now,
            prompt_name=EXTRACT_RULES_PROMPT_NAME,
            prompt_version=EXTRACT_RULES_VERSION,
            model_id=OPUS_MODEL_ID,
        )
        report = draft.to_pending_review()
        self._report_repo.save(report)
        logger.info(
            "ingestion report persisted: report_id=%s trace_id=%s status=%s",
            report_id,
            trace_id,
            report.status,
        )
        return report_id
