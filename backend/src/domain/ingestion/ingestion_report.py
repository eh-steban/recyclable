"""IngestionReport aggregate root.

Non-trivial aggregate root per architecture.md § Aggregates.
The `to_pending_review()` method runs `IngestionReportValidator` (notification-
handler style) and refuses the transition on any violation.

Per architecture.md § Three-level validation, the Validator enforces
Level-2 whole-object checks: every proposed change must carry op, rule,
confidence, non-null source_document_id, and non-empty source_quote;
trace_id and jurisdiction_id must be non-null (INV-DATA-001).

Cross-entity references are by typed id only (architecture.md § Aggregates).
"""

# LLM-extracted rule payloads are dict[str, Any]; boundary guard reads fields
# via getattr, which is also typed Any -- no tighter type is available here.
# pyright: reportExplicitAny=false, reportAny=false

import dataclasses
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, cast, override

from src.domain.knowledge_base.jurisdiction import JurisdictionId


@dataclass(frozen=True, slots=True)
class IngestionReportId:
    """Typed identity Value for IngestionReport."""

    value: uuid.UUID

    @override
    def __str__(self) -> str:
        return str(self.value)


class IngestionReportStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class RuleOp(StrEnum):
    ADD = "add"
    UPDATE = "update"


@dataclass(frozen=True, slots=True)
class ProposedRuleChange:
    """A single candidate rule change extracted from a source document.

    INV-DATA-001: source_document_id and source_quote must be non-null/
    non-empty. Enforced by IngestionReportValidator at `to_pending_review()`
    time, not at construction, so the aggregate can be assembled incrementally
    from LLM output and then validated as a whole.

    `rule` is an open JSON-compatible dict of proposed rule fields; typed as
    dict[str, Any] because the exact shape depends on what Opus extracts.
    """

    op: RuleOp
    rule: dict[str, Any]
    confidence: str
    source_document_id: uuid.UUID | None
    source_quote: str


class IngestionReportValidationError(Exception):
    """Raised by `to_pending_review()` when the Validator finds violations.

    Carries all violations (notification-handler style) so the caller can
    present the full failure set rather than first-error-only.
    """

    violations: list[str]

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__(f"IngestionReport validation failed: {violations}")


def _validate_to_pending_review(report: IngestionReport) -> list[str]:
    """Collect all violations for the draft -> pending_review transition.

    Returns an empty list when the report is valid.
    """
    violations: list[str] = []

    _allowed = (
        IngestionReportStatus.DRAFT,
        IngestionReportStatus.PENDING_REVIEW,
    )
    if report.status not in _allowed:
        _msg = (
            f"status must be DRAFT or PENDING_REVIEW to call"
            f" to_pending_review(); got {report.status!r}"
        )
        violations.append(_msg)

    if report.jurisdiction_id is None:
        violations.append("jurisdiction_id must be non-null")

    if report.trace_id is None:
        violations.append("trace_id must be non-null")

    for i, change in enumerate(report.proposed_rule_changes):
        prefix = f"proposed_rule_changes[{i}]"
        if change.source_document_id is None:
            violations.append(f"{prefix}.source_document_id must be non-null")
        if not change.source_quote:
            violations.append(
                f"{prefix}.source_quote must be non-null and non-empty"
            )

    return violations


@dataclass(frozen=True, slots=True)
class IngestionReport:
    """IngestionReport aggregate root.

    Represents one operator-initiated ingestion run: fetch one or more source
    pages, extract candidate rules, and produce a reviewable report.

    Fields:
        id: typed identity, minted by repo.next_identity().
        jurisdiction_id: the jurisdiction this run targets (typed id).
        trace_id: FK to the IngestionRunTrace minted at run start; non-null.
        seed_url: the URL the run was seeded with.
        proposed_rule_changes: immutable tuple of candidate changes.
        conflicts: immutable tuple of detected conflicts with active rules.
        missing_fields: field names the agent could not extract.
        status: lifecycle status (draft -> pending_review -> approved|rejected).
        created_at: UTC timestamp.
    """

    id: IngestionReportId
    jurisdiction_id: JurisdictionId | None
    trace_id: uuid.UUID | None
    seed_url: str
    proposed_rule_changes: tuple[ProposedRuleChange, ...]
    conflicts: tuple[dict[str, Any], ...]
    missing_fields: tuple[str, ...]
    status: IngestionReportStatus
    created_at: datetime
    decided_at: datetime | None = field(default=None)
    reviewer_id: str | None = field(default=None)
    prompt_name: str | None = field(default=None)
    prompt_version: int | None = field(default=None)
    model_id: str | None = field(default=None)

    def __post_init__(self) -> None:
        # Tuple boundary-guard: ORM/LLM adapters may supply a list; reject it
        # at the boundary. The cast(object, ...) defeats type-checker narrowing
        # so the isinstance check is a real runtime guard (architecture.md
        # § Tuple boundary-guard idiom). Policy is reject, never coerce.
        for attr in ("proposed_rule_changes", "conflicts", "missing_fields"):
            val = getattr(self, attr)
            if not isinstance(cast(object, val), tuple):
                msg = f"IngestionReport.{attr} must be a tuple, got {type(val)}"
                raise TypeError(msg)

    def to_pending_review(self) -> IngestionReport:
        """Transition from draft to pending_review.

        Runs IngestionReportValidator (notification-handler style); raises
        IngestionReportValidationError collecting all violations if any are
        found. Returns a new frozen IngestionReport with status updated.
        """
        violations = _validate_to_pending_review(self)
        if violations:
            raise IngestionReportValidationError(violations)
        return dataclasses.replace(
            self, status=IngestionReportStatus.PENDING_REVIEW
        )
