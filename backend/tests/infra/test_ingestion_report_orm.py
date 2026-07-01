"""Integration tests for IngestionReport and IngestionRunTrace ORM + repos.

Verifies round-trip persistence: a report with proposed_rule_changes and
conflicts survives save() -> find_by_id() with no field loss.
Also verifies find_pending() returns only pending_review reports.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from src.domain.ingestion.ingestion_report import (
    IngestionReport,
    IngestionReportStatus,
    ProposedRuleChange,
    RuleOp,
)
from src.domain.ingestion.ingestion_run_trace import (
    IngestionRunTrace,
    IngestionRunTraceId,
)
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.infra.db.repos.ingestion_report_repo import PgIngestionReportRepo
from src.infra.db.repos.ingestion_run_trace_repo import PgIngestionRunTraceRepo
from src.infra.db.repos.jurisdiction_repo import PgJurisdictionRepo
from tests.utils.builders.knowledge_base import make_jurisdiction


@pytest.fixture()
def jurisdiction_id(db_session: Session) -> JurisdictionId:
    repo = PgJurisdictionRepo(db_session)
    jur = make_jurisdiction()
    repo.save(jur)
    return jur.id


@pytest.fixture()
def trace_repo(db_session: Session) -> PgIngestionRunTraceRepo:
    return PgIngestionRunTraceRepo(db_session)


@pytest.fixture()
def report_repo(db_session: Session) -> PgIngestionReportRepo:
    return PgIngestionReportRepo(db_session)


def _make_trace(trace_repo: PgIngestionRunTraceRepo) -> IngestionRunTrace:
    trace_id = trace_repo.next_identity()
    trace = IngestionRunTrace(
        id=trace_id,
        seed_url="https://denvergov.org/recycling",
        created_at=datetime.now(tz=UTC),
    )
    trace_repo.save(trace)
    return trace


def _make_report(
    report_repo: PgIngestionReportRepo,
    jurisdiction_id: JurisdictionId,
    trace_id: IngestionRunTraceId,
    *,
    status: IngestionReportStatus = IngestionReportStatus.DRAFT,
    proposed_rule_changes: tuple[ProposedRuleChange, ...] = (),
) -> IngestionReport:
    report = IngestionReport(
        id=report_repo.next_identity(),
        jurisdiction_id=jurisdiction_id,
        trace_id=trace_id.value,
        seed_url="https://denvergov.org/recycling",
        proposed_rule_changes=proposed_rule_changes,
        conflicts=(),
        missing_fields=(),
        status=status,
        created_at=datetime.now(tz=UTC),
    )
    report_repo.save(report)
    return report


@pytest.mark.integration
def test_ingestion_run_trace_round_trips(
    trace_repo: PgIngestionRunTraceRepo,
) -> None:
    """IngestionRunTrace saves and loads with no field loss."""
    trace = _make_trace(trace_repo)
    loaded = trace_repo.find_by_id(trace.id)
    assert loaded is not None
    assert loaded.id == trace.id
    assert loaded.seed_url == trace.seed_url


@pytest.mark.integration
def test_ingestion_report_round_trips(
    report_repo: PgIngestionReportRepo,
    trace_repo: PgIngestionRunTraceRepo,
    jurisdiction_id: JurisdictionId,
) -> None:
    """IngestionReport saves and loads with proposed_rule_changes intact."""
    trace = _make_trace(trace_repo)
    change = ProposedRuleChange(
        op=RuleOp.ADD,
        rule={"disposition": "curbside_recycle", "accepted_status": "accepted"},
        confidence="high",
        source_document_id=uuid.uuid4(),
        source_quote="All glass bottles are accepted curbside.",
    )
    report = _make_report(
        report_repo,
        jurisdiction_id,
        trace.id,
        proposed_rule_changes=(change,),
    )

    loaded = report_repo.find_by_id(report.id)
    assert loaded is not None
    assert loaded.id == report.id
    assert loaded.jurisdiction_id == jurisdiction_id
    assert loaded.trace_id == trace.id.value
    assert len(loaded.proposed_rule_changes) == 1
    loaded_change = loaded.proposed_rule_changes[0]
    assert loaded_change.op == RuleOp.ADD
    assert loaded_change.confidence == "high"
    assert loaded_change.source_quote == change.source_quote


@pytest.mark.integration
def test_find_pending_returns_only_pending_review(
    report_repo: PgIngestionReportRepo,
    trace_repo: PgIngestionRunTraceRepo,
    jurisdiction_id: JurisdictionId,
) -> None:
    """find_pending() returns only pending_review reports."""
    trace1 = _make_trace(trace_repo)
    trace2 = _make_trace(trace_repo)

    draft = _make_report(
        report_repo,
        jurisdiction_id,
        trace1.id,
        status=IngestionReportStatus.DRAFT,
    )
    pending = _make_report(
        report_repo,
        jurisdiction_id,
        trace2.id,
        status=IngestionReportStatus.PENDING_REVIEW,
    )

    results = report_repo.find_pending()
    result_ids = {r.id for r in results}
    assert pending.id in result_ids
    assert draft.id not in result_ids
