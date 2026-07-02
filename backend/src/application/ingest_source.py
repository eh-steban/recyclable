"""IngestSource application service -- ingestion worker task coordinator.

Pipeline:
1. Mint a trace identity and persist an IngestionRunTrace.
2. Fetch the seed URL via SourceFetcher.
3. Call IngestionLLM.extract() to get CandidateRule list.
4. Assemble an IngestionReport (all candidates op=add; no diff yet).
5. Transition to pending_review (runs Validator).
6. Persist the report.
7. Return the IngestionReportId.

The trace save (step 1) and report save (step 6) are committed in two
separate DB transactions; the fetch + LLM extraction (steps 2-3) run
with no open transaction (repositories.md Principle 9).

Imports domain ports only; never imports infra/ (DDD inward-dependency rule).
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
from src.domain.ingestion.ingestion_run_trace import IngestionRunTrace
from src.domain.ingestion.ingestion_run_trace_repo import IngestionRunTraceRepo
from src.domain.ingestion.source_fetcher import SourceFetcher
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

    def run(self, command: IngestSourceCommand) -> IngestionReportId:
        """Execute the single-URL ingestion pipeline.

        Returns the IngestionReportId of the persisted pending_review report.
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

        proposed_changes = tuple(_candidate_to_change(c) for c in candidates)
        report_id = self._report_repo.next_identity()
        draft = IngestionReport(
            id=report_id,
            jurisdiction_id=command.jurisdiction_id,
            trace_id=trace_id.value,
            seed_url=command.seed_url,
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
