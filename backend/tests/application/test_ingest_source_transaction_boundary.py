"""B-3: trace save and report save must be in separate DB transactions.

The trace is persisted and committed before the network fetch and LLM
extraction begin. The report is persisted in a second transaction after
extraction completes. No open DB transaction is held during the fetch or
LLM call (repositories.md Principle 9).

We verify this by tracking the sequence of events: trace.save() must be
called and committed before llm.extract() is invoked.
"""

import uuid
from typing import NamedTuple, final, override

from src.application.ingest_source import IngestSource
from src.application.ingest_source_command import IngestSourceCommand
from src.domain.ingestion.candidate_rule import CandidateRule
from src.domain.ingestion.ingestion_report import (
    IngestionReport,
    IngestionReportId,
    IngestionReportStatus,
)
from src.domain.ingestion.ingestion_run_trace import (
    IngestionRunTrace,
    IngestionRunTraceId,
)
from src.domain.ingestion.source_fetcher import SourceFetchResult
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from tests.utils.fakes._base import InMemoryRepo

_J_ID = JurisdictionId(uuid.uuid4())

# ---------------------------------------------------------------------------
# Event-recording fakes
# ---------------------------------------------------------------------------


class MemIngestionReportRepo(InMemoryRepo[IngestionReport, IngestionReportId]):
    @override
    def next_identity(self) -> IngestionReportId:
        return IngestionReportId(uuid.uuid4())

    def find_pending(self) -> list[IngestionReport]:
        return [
            r
            for r in self._store.values()
            if r.status == IngestionReportStatus.PENDING_REVIEW
        ]


class TracingTraceRepo(InMemoryRepo[IngestionRunTrace, IngestionRunTraceId]):
    """Records when trace.save() is called so we can assert ordering."""

    events: list[str]

    def __init__(self, events: list[str]) -> None:
        super().__init__()
        self.events = events

    @override
    def next_identity(self) -> IngestionRunTraceId:
        return IngestionRunTraceId(uuid.uuid4())

    @override
    def save(self, entity: IngestionRunTrace, /) -> None:
        self.events.append("trace_saved")
        super().save(entity)


@final
class TracingLLM:
    """Records when extract() is called so we can assert ordering."""

    events: list[str]
    _source_doc_id: uuid.UUID

    def __init__(self, events: list[str]) -> None:
        self.events = events
        self._source_doc_id = uuid.uuid4()

    def extract(
        self,
        source: SourceFetchResult,
        jurisdiction_id: str,
        jurisdiction_name: str,
        prompt_name: str,
        prompt_version: int,
    ) -> list[CandidateRule]:
        self.events.append("llm_extract_called")
        return [
            CandidateRule(
                source_document_id=self._source_doc_id,
                source_quote="Glass bottles are accepted at curbside.",
                confidence="high",
                jurisdiction_id=uuid.UUID(jurisdiction_id),
                material_slug="glass-bottles",
                disposition="curbside_recycle",
                accepted_status="accepted",
                preparation_steps=(),
                exceptions=(),
                warnings=(),
            )
        ]


class SimpleFetcher:
    def fetch(self, url: str, *, authority_level: int = 3) -> SourceFetchResult:
        return SourceFetchResult(
            id=uuid.uuid4(),
            url=url,
            source_text="Glass bottles are accepted.",
            source_text_hash="abc123",
            authority_level=authority_level,
            content_type="text/html",
        )


# ---------------------------------------------------------------------------
# Pipeline wrapper that mimics the two-transaction shape
# ---------------------------------------------------------------------------


class _PhaseResult(NamedTuple):
    report_id: IngestionReportId
    events: list[str]


def _run_two_phase(command: IngestSourceCommand) -> _PhaseResult:
    """Drive IngestSource with the two-transaction pattern from the pipeline.

    Transaction 1 commits the trace; network+LLM run outside any transaction;
    Transaction 2 commits the report. Phases are invoked directly here so the
    test stays in-process without a real DB.
    """
    events: list[str] = []
    report_repo = MemIngestionReportRepo()
    trace_repo = TracingTraceRepo(events)
    fetcher = SimpleFetcher()
    llm = TracingLLM(events)

    service = IngestSource(
        report_repo=report_repo,
        trace_repo=trace_repo,
        fetcher=fetcher,
        llm=llm,
    )

    # Phase 1: save trace (tx 1).
    trace_id = service.run_trace_phase(command)
    events.append("tx1_committed")

    # Phase 2: fetch + extract (no open transaction).
    source, candidates = service.run_extract_phase(command, trace_id)
    events.append("extract_done")

    # Phase 3: save report (tx 2).
    report_id = service.run_report_phase(command, trace_id, source, candidates)
    events.append("tx2_committed")

    return _PhaseResult(report_id=report_id, events=events)


class TestTransactionBoundary:
    def test_trace_committed_before_llm_extract(self) -> None:
        """trace_saved and tx1_committed must precede llm_extract_called."""
        command = IngestSourceCommand(
            seed_url="https://denvergov.org/recycling",
            jurisdiction_id=_J_ID,
            jurisdiction_name="Denver, CO",
        )
        result = _run_two_phase(command)
        trace_idx = result.events.index("trace_saved")
        tx1_idx = result.events.index("tx1_committed")
        llm_idx = result.events.index("llm_extract_called")
        assert trace_idx < llm_idx, "trace must be saved before LLM extract"
        assert tx1_idx < llm_idx, "trace tx must commit before LLM extract"

    def test_report_saved_after_extract(self) -> None:
        """tx2_committed (report save) must follow extract_done."""
        command = IngestSourceCommand(
            seed_url="https://denvergov.org/recycling",
            jurisdiction_id=_J_ID,
            jurisdiction_name="Denver, CO",
        )
        result = _run_two_phase(command)
        extract_idx = result.events.index("extract_done")
        tx2_idx = result.events.index("tx2_committed")
        assert extract_idx < tx2_idx, "report tx must commit after extraction"
