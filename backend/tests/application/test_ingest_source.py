"""Tests for the IngestSource application service.

Verifies the full coordination path:
- Mints trace + report identities via repos
- Delegates to IngestionLLM for extraction
- Assembles all candidates as op=add (no diff step yet)
- Runs Validator and transitions report to pending_review
- Persists report + trace
- Returns the IngestionReportId
"""

import uuid
from typing import final, override

import pytest

from src.application.ingest_source import IngestSource
from src.application.ingest_source_command import IngestSourceCommand
from src.domain.ingestion.candidate_rule import CandidateRule
from src.domain.ingestion.ingestion_report import (
    IngestionReport,
    IngestionReportId,
    IngestionReportStatus,
    RuleOp,
)
from src.domain.ingestion.ingestion_run_trace import (
    IngestionRunTrace,
    IngestionRunTraceId,
)
from src.domain.ingestion.source_fetcher import SourceFetchResult
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from tests.utils.fakes._base import InMemoryRepo

# ---------------------------------------------------------------------------
# In-memory fakes for the ingestion repos
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


class MemIngestionRunTraceRepo(
    InMemoryRepo[IngestionRunTrace, IngestionRunTraceId]
):
    @override
    def next_identity(self) -> IngestionRunTraceId:
        return IngestionRunTraceId(uuid.uuid4())


# ---------------------------------------------------------------------------
# Fake IngestionLLM
# ---------------------------------------------------------------------------


@final
class FakeIngestionLLM:
    """Returns a single high-confidence candidate."""

    _source_doc_id: uuid.UUID

    def __init__(self, source_doc_id: uuid.UUID) -> None:
        self._source_doc_id = source_doc_id

    def extract(
        self,
        source: SourceFetchResult,
        jurisdiction_id: str,
        jurisdiction_name: str,
        prompt_name: str,
        prompt_version: int,
    ) -> list[CandidateRule]:
        return [
            CandidateRule(
                source_document_id=self._source_doc_id,
                source_quote="Glass bottles are accepted at curbside.",
                confidence="high",
                jurisdiction_id=uuid.UUID(jurisdiction_id),
                material_slug="glass-bottles",
                disposition="curbside_recycle",
                accepted_status="accepted",
                preparation_steps=("Empty and rinse",),
                exceptions=(),
                warnings=(),
            )
        ]


class FakeSourceFetcher:
    """Returns a minimal SourceFetchResult without real HTTP."""

    def fetch(self, url: str, *, authority_level: int = 3) -> SourceFetchResult:
        doc_id = uuid.uuid4()
        return SourceFetchResult(
            id=doc_id,
            url=url,
            source_text="Glass bottles are accepted at curbside.",
            source_text_hash="abc123",
            authority_level=authority_level,
            content_type="text/html",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_J_ID = JurisdictionId(uuid.uuid4())


@pytest.fixture()
def report_repo() -> MemIngestionReportRepo:
    return MemIngestionReportRepo()


@pytest.fixture()
def trace_repo() -> MemIngestionRunTraceRepo:
    return MemIngestionRunTraceRepo()


@pytest.fixture()
def fetcher() -> FakeSourceFetcher:
    return FakeSourceFetcher()


def _make_service(
    report_repo: MemIngestionReportRepo,
    trace_repo: MemIngestionRunTraceRepo,
    fetcher: FakeSourceFetcher,
    llm: FakeIngestionLLM | None = None,
) -> IngestSource:
    if llm is None:
        llm = FakeIngestionLLM(uuid.uuid4())
    return IngestSource(
        report_repo=report_repo,
        trace_repo=trace_repo,
        fetcher=fetcher,
        llm=llm,
    )


def _run_pipeline(
    service: IngestSource,
    command: IngestSourceCommand,
) -> IngestionReportId:
    """Drive all three phases in sequence (mirrors the pipeline shape)."""
    trace_id = service.run_trace_phase(command)
    source, candidates = service.run_extract_phase(command, trace_id)
    return service.run_report_phase(command, trace_id, source, candidates)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestIngestSource:
    def test_returns_report_id(
        self,
        report_repo: MemIngestionReportRepo,
        trace_repo: MemIngestionRunTraceRepo,
        fetcher: FakeSourceFetcher,
    ) -> None:
        """Three-phase run returns an IngestionReportId."""
        service = _make_service(report_repo, trace_repo, fetcher)
        command = IngestSourceCommand(
            seed_url="https://denvergov.org/recycling",
            jurisdiction_id=_J_ID,
            jurisdiction_name="Denver, CO",
        )
        report_id = _run_pipeline(service, command)
        assert isinstance(report_id, IngestionReportId)

    def test_report_persisted_as_pending_review(
        self,
        report_repo: MemIngestionReportRepo,
        trace_repo: MemIngestionRunTraceRepo,
        fetcher: FakeSourceFetcher,
    ) -> None:
        """The persisted report has status pending_review."""
        service = _make_service(report_repo, trace_repo, fetcher)
        command = IngestSourceCommand(
            seed_url="https://denvergov.org/recycling",
            jurisdiction_id=_J_ID,
            jurisdiction_name="Denver, CO",
        )
        report_id = _run_pipeline(service, command)
        report = report_repo.find_by_id(report_id)
        assert report is not None
        assert report.status == IngestionReportStatus.PENDING_REVIEW

    def test_candidates_bucketed_as_op_add(
        self,
        report_repo: MemIngestionReportRepo,
        trace_repo: MemIngestionRunTraceRepo,
        fetcher: FakeSourceFetcher,
    ) -> None:
        """All candidates are op=add (no diff step yet)."""
        service = _make_service(report_repo, trace_repo, fetcher)
        command = IngestSourceCommand(
            seed_url="https://denvergov.org/recycling",
            jurisdiction_id=_J_ID,
            jurisdiction_name="Denver, CO",
        )
        report_id = _run_pipeline(service, command)
        report = report_repo.find_by_id(report_id)
        assert report is not None
        assert len(report.proposed_rule_changes) == 1
        assert report.proposed_rule_changes[0].op == RuleOp.ADD

    def test_trace_minted_and_linked(
        self,
        report_repo: MemIngestionReportRepo,
        trace_repo: MemIngestionRunTraceRepo,
        fetcher: FakeSourceFetcher,
    ) -> None:
        """The report's trace_id resolves to a persisted trace."""
        service = _make_service(report_repo, trace_repo, fetcher)
        command = IngestSourceCommand(
            seed_url="https://denvergov.org/recycling",
            jurisdiction_id=_J_ID,
            jurisdiction_name="Denver, CO",
        )
        report_id = _run_pipeline(service, command)
        report = report_repo.find_by_id(report_id)
        assert report is not None
        assert report.trace_id is not None
        trace = trace_repo.find_by_id(IngestionRunTraceId(report.trace_id))
        assert trace is not None
        assert trace.seed_url == command.seed_url


# ---------------------------------------------------------------------------
# Error-path tests
# ---------------------------------------------------------------------------


class BoomFetcher:
    """Raises on fetch()."""

    def fetch(self, url: str, *, authority_level: int = 3) -> SourceFetchResult:
        raise RuntimeError("network failure")


class BoomLLM:
    """Raises on extract()."""

    def extract(
        self,
        source: SourceFetchResult,
        jurisdiction_id: str,
        jurisdiction_name: str,
        prompt_name: str,
        prompt_version: int,
    ) -> list[CandidateRule]:
        raise RuntimeError("LLM timeout")


@final
class EmptyLLM:
    """Returns no candidates."""

    def extract(
        self,
        source: SourceFetchResult,
        jurisdiction_id: str,
        jurisdiction_name: str,
        prompt_name: str,
        prompt_version: int,
    ) -> list[CandidateRule]:
        return []


class BoomReportRepo(InMemoryRepo[IngestionReport, IngestionReportId]):
    @override
    def next_identity(self) -> IngestionReportId:
        return IngestionReportId(uuid.uuid4())

    def find_pending(self) -> list[IngestionReport]:
        return []

    @override
    def save(self, entity: IngestionReport, /) -> None:
        raise RuntimeError("DB write failed")


class TestIngestSourceErrorPaths:
    def test_fetcher_raises_propagates(
        self,
        report_repo: MemIngestionReportRepo,
        trace_repo: MemIngestionRunTraceRepo,
    ) -> None:
        """fetch() raising propagates; no report is saved."""
        service = IngestSource(
            report_repo=report_repo,
            trace_repo=trace_repo,
            fetcher=BoomFetcher(),
            llm=FakeIngestionLLM(uuid.uuid4()),
        )
        command = IngestSourceCommand(
            seed_url="https://denvergov.org/recycling",
            jurisdiction_id=_J_ID,
            jurisdiction_name="Denver, CO",
        )
        trace_id = service.run_trace_phase(command)
        with pytest.raises(RuntimeError, match="network failure"):
            service.run_extract_phase(command, trace_id)
        assert list(report_repo._store.values()) == []

    def test_llm_raises_propagates(
        self,
        report_repo: MemIngestionReportRepo,
        trace_repo: MemIngestionRunTraceRepo,
        fetcher: FakeSourceFetcher,
    ) -> None:
        """extract() raising propagates; no report is saved."""
        service = IngestSource(
            report_repo=report_repo,
            trace_repo=trace_repo,
            fetcher=fetcher,
            llm=BoomLLM(),
        )
        command = IngestSourceCommand(
            seed_url="https://denvergov.org/recycling",
            jurisdiction_id=_J_ID,
            jurisdiction_name="Denver, CO",
        )
        trace_id = service.run_trace_phase(command)
        with pytest.raises(RuntimeError, match="LLM timeout"):
            service.run_extract_phase(command, trace_id)
        assert list(report_repo._store.values()) == []

    def test_empty_candidates_yields_pending_review_with_zero_changes(
        self,
        report_repo: MemIngestionReportRepo,
        trace_repo: MemIngestionRunTraceRepo,
        fetcher: FakeSourceFetcher,
    ) -> None:
        """Empty candidate list yields PENDING_REVIEW with zero changes."""
        service = IngestSource(
            report_repo=report_repo,
            trace_repo=trace_repo,
            fetcher=fetcher,
            llm=EmptyLLM(),
        )
        command = IngestSourceCommand(
            seed_url="https://denvergov.org/recycling",
            jurisdiction_id=_J_ID,
            jurisdiction_name="Denver, CO",
        )
        trace_id = service.run_trace_phase(command)
        source, candidates = service.run_extract_phase(command, trace_id)
        assert candidates == []
        report_id = service.run_report_phase(
            command, trace_id, source, candidates
        )
        report = report_repo.find_by_id(report_id)
        assert report is not None
        assert report.status == IngestionReportStatus.PENDING_REVIEW
        assert len(report.proposed_rule_changes) == 0

    def test_report_repo_save_raises_propagates(
        self,
        trace_repo: MemIngestionRunTraceRepo,
        fetcher: FakeSourceFetcher,
    ) -> None:
        """report_repo.save() raising propagates out of run_report_phase()."""
        boom_repo = BoomReportRepo()
        service = IngestSource(
            report_repo=boom_repo,
            trace_repo=trace_repo,
            fetcher=fetcher,
            llm=FakeIngestionLLM(uuid.uuid4()),
        )
        command = IngestSourceCommand(
            seed_url="https://denvergov.org/recycling",
            jurisdiction_id=_J_ID,
            jurisdiction_name="Denver, CO",
        )
        trace_id = service.run_trace_phase(command)
        source, candidates = service.run_extract_phase(command, trace_id)
        with pytest.raises(RuntimeError, match="DB write failed"):
            service.run_report_phase(command, trace_id, source, candidates)
