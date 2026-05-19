"""AnswerAuditRecord aggregate root.

Non-trivial aggregate root per architecture.md § Aggregates.
The constructor enforces INV-PROD-001 by running
AnswerAuditRecordValidator; a violation raises
AnswerAuditRecordValidationError (documented in domain/exceptions.py).

Per architecture.md § Three-level validation, this is the Level-2
whole-object check.

Identity: AnswerAuditRecordId (UUID Value Object), minted by
repo.next_identity() before construction.

Per design D7 (persistence-oriented repo + next_identity() seam):
the application service mints the id, constructs the record
(constructor enforces INV-PROD-001), then calls save().
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import cast, override

from src.domain.audit.answer_audit_record_validator import (
    validate_answer_audit_record,
)
from src.domain.exceptions import AnswerAuditRecordValidationError
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.retrieval.citation import Citation
from src.domain.retrieval.evaluated_answer import NoEvaluationReason
from src.domain.retrieval.item_verdict import ItemVerdict

# ---------------------------------------------------------------------------
# Typed identity Value
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AnswerAuditRecordId:
    """Typed identity Value for AnswerAuditRecord."""

    value: uuid.UUID

    @override
    def __str__(self) -> str:
        return str(self.value)


# ---------------------------------------------------------------------------
# Aggregate Root
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AnswerAuditRecord:
    """AnswerAuditRecord aggregate root.

    Append-only audit entry per user-path query. Every answered query
    writes one record before the response is returned to the caller.

    The constructor enforces INV-PROD-001 (via AnswerAuditRecordValidator):
    a definitive verdict must have non-empty citations whose URLs are all
    members of retrieved_source_urls.

    Fields:
        id: typed identity, minted by repo.next_identity().
        query_text: the raw user question text.
        query_location_input: the raw user location input.
        jurisdiction_id: resolved JurisdictionId (typed id, not object ref).
        verdict: the domain verdict (Accepted | Refused | NotCovered |
                 Conflicted).
        citations: source citations supporting the verdict.
        retrieved_source_urls: the URL set from the rule retrieval query;
                               stored here so the validator can check
                               provenance at construction and at replay.
        recommended_action: short actionable text.
        prompt_version: versioned prompt name (e.g. "ask_compose_v1").
        model_id: the model used for this call (INV-LLM-005).
        latency_ms: total end-to-end latency in milliseconds.
        created_at: UTC timestamp.
        no_evaluation_reason: set when this record represents a
                              NoEvaluation outcome; None for evaluated
                              outcomes. Used by the repo to persist the
                              correct outcome_kind and reason enum value.
    """

    id: AnswerAuditRecordId
    query_text: str
    query_location_input: str
    jurisdiction_id: JurisdictionId
    verdict: ItemVerdict
    citations: tuple[Citation, ...]
    retrieved_source_urls: frozenset[str]
    recommended_action: str
    prompt_version: str
    model_id: str
    latency_ms: int
    created_at: datetime
    no_evaluation_reason: NoEvaluationReason | None = field(default=None)

    def __post_init__(self) -> None:
        # Runtime boundary guard: cast(object, ...) keeps this a real check
        # despite the declared tuple type. See private/learnings.md
        # (tuple boundary-guard idiom).
        if not isinstance(cast(object, self.citations), tuple):
            kind = type(self.citations).__name__
            raise TypeError(
                f"AnswerAuditRecord.citations must be a tuple, got {kind}"
            )
        # Level-2 whole-object validation (architecture.md § Three-level
        # validation). Runs AnswerAuditRecordValidator inline; violation
        # raises AnswerAuditRecordValidationError.
        violations = validate_answer_audit_record(
            self.verdict,
            self.citations,
            self.retrieved_source_urls,
        )
        if violations:
            raise AnswerAuditRecordValidationError(violations)
