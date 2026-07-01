"""Tests for IngestionReport aggregate, IngestionReportId, and Validator.

Verifies:
- Valid construction and typed-id minting
- to_pending_review() enforces Validator invariants (INV-DATA-001):
  every entry needs op, rule fields, confidence, non-null source_document_id,
  non-null/non-empty source_quote; trace_id non-null; jurisdiction_id non-null
- Notification-handler style: all violations collected, not thrown on first
- Tuple boundary-guard on frozen tuple fields (architecture.md idiom)
"""

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest

from src.domain.ingestion.ingestion_report import (
    IngestionReport,
    IngestionReportId,
    IngestionReportStatus,
    IngestionReportValidationError,
    ProposedRuleChange,
    RuleOp,
)
from src.domain.knowledge_base.jurisdiction import JurisdictionId

_J_ID = JurisdictionId(uuid.uuid4())
_TRACE_ID = uuid.uuid4()
_SOURCE_DOC_ID = uuid.uuid4()
_NOW = datetime.now(tz=UTC)


def _valid_change() -> ProposedRuleChange:
    return ProposedRuleChange(
        op=RuleOp.ADD,
        rule={"disposition": "curbside_recycle", "accepted_status": "accepted"},
        confidence="high",
        source_document_id=_SOURCE_DOC_ID,
        source_quote="All glass bottles are accepted curbside.",
    )


def _make_report(
    *,
    jurisdiction_id: JurisdictionId | None = _J_ID,
    trace_id: uuid.UUID | None = _TRACE_ID,
    proposed_rule_changes: tuple[ProposedRuleChange, ...] | None = None,
    seed_url: str = "https://denvergov.org/recycling",
) -> IngestionReport:
    if proposed_rule_changes is None:
        proposed_rule_changes = ()
    return IngestionReport(
        id=IngestionReportId(uuid.uuid4()),
        jurisdiction_id=jurisdiction_id,
        trace_id=trace_id,
        seed_url=seed_url,
        proposed_rule_changes=proposed_rule_changes,
        conflicts=(),
        missing_fields=(),
        status=IngestionReportStatus.DRAFT,
        created_at=_NOW,
    )


class TestIngestionReportId:
    def test_typed_id_str(self) -> None:
        uid = uuid.uuid4()
        assert str(IngestionReportId(uid)) == str(uid)

    def test_equality_by_value(self) -> None:
        uid = uuid.uuid4()
        assert IngestionReportId(uid) == IngestionReportId(uid)
        assert IngestionReportId(uid) != IngestionReportId(uuid.uuid4())


class TestIngestionReportConstruction:
    def test_valid_draft_report_constructs(self) -> None:
        report = _make_report()
        assert report.status == IngestionReportStatus.DRAFT
        assert report.jurisdiction_id == _J_ID

    def test_proposed_rule_changes_tuple_boundary_guard(self) -> None:
        """list passed to a frozen tuple field is rejected at construction."""
        with pytest.raises(TypeError):
            IngestionReport(
                id=IngestionReportId(uuid.uuid4()),
                jurisdiction_id=_J_ID,
                trace_id=_TRACE_ID,
                seed_url="https://example.com",
                # Double-cast through object so basedpyright accepts passing
                # a list where a tuple is declared; we're testing the runtime
                # boundary guard (architecture.md § Tuple boundary-guard idiom).
                proposed_rule_changes=cast(
                    tuple[ProposedRuleChange, ...],
                    cast(object, [_valid_change()]),
                ),
                conflicts=(),
                missing_fields=(),
                status=IngestionReportStatus.DRAFT,
                created_at=_NOW,
            )


class TestToPendingReview:
    def test_clean_report_transitions_to_pending_review(self) -> None:
        report = _make_report(proposed_rule_changes=(_valid_change(),))
        transitioned = report.to_pending_review()
        assert transitioned.status == IngestionReportStatus.PENDING_REVIEW

    def test_missing_jurisdiction_id_collected(self) -> None:
        report = _make_report(jurisdiction_id=None)
        with pytest.raises(IngestionReportValidationError) as exc_info:
            report.to_pending_review()
        violations = exc_info.value.violations
        assert any("jurisdiction_id" in v for v in violations)

    def test_missing_trace_id_collected(self) -> None:
        report = _make_report(trace_id=None)
        with pytest.raises(IngestionReportValidationError) as exc_info:
            report.to_pending_review()
        violations = exc_info.value.violations
        assert any("trace_id" in v for v in violations)

    def test_entry_missing_source_quote_collected(self) -> None:
        bad_change = ProposedRuleChange(
            op=RuleOp.ADD,
            rule={"disposition": "curbside_recycle"},
            confidence="high",
            source_document_id=_SOURCE_DOC_ID,
            source_quote="",  # empty -- violation
        )
        report = _make_report(proposed_rule_changes=(bad_change,))
        with pytest.raises(IngestionReportValidationError) as exc_info:
            report.to_pending_review()
        violations = exc_info.value.violations
        assert any("source_quote" in v for v in violations)

    def test_entry_missing_source_document_id_collected(self) -> None:
        bad_change = ProposedRuleChange(
            op=RuleOp.ADD,
            rule={"disposition": "curbside_recycle"},
            confidence="high",
            source_document_id=None,
            source_quote="Glass bottles accepted curbside.",
        )
        report = _make_report(proposed_rule_changes=(bad_change,))
        with pytest.raises(IngestionReportValidationError) as exc_info:
            report.to_pending_review()
        violations = exc_info.value.violations
        assert any("source_document_id" in v for v in violations)

    def test_multiple_violations_all_collected(self) -> None:
        """All violations are collected, not just the first."""
        bad_change = ProposedRuleChange(
            op=RuleOp.ADD,
            rule={},
            confidence="high",
            source_document_id=None,
            source_quote="",
        )
        report = _make_report(
            jurisdiction_id=None,
            trace_id=None,
            proposed_rule_changes=(bad_change,),
        )
        with pytest.raises(IngestionReportValidationError) as exc_info:
            report.to_pending_review()
        # Must collect: jurisdiction_id, trace_id, source_document_id,
        # source_quote -- at minimum 4 violations
        assert len(exc_info.value.violations) >= 4

    def test_already_pending_review_idempotent(self) -> None:
        report = _make_report(proposed_rule_changes=(_valid_change(),))
        once = report.to_pending_review()
        twice = once.to_pending_review()
        assert twice.status == IngestionReportStatus.PENDING_REVIEW
