"""Domain -> wire mapper for the user path.

Maps EvaluatedAnswer | NoEvaluation to the wire Answer shape per
private/specs/contracts/answer.md § Verdict mapping.

The ItemVerdict -> short_answer mapping is sum-complete: the final
match arm uses assert_never so basedpyright flags missing arms at
lint time (INV-LLM-001, INV-PROD-001).

Multiple NoEvaluationReason values intentionally collapse to
short_answer='unknown'; the audit record carries the precise cause.
See private/learnings.md (wire-shape lossiness vs. audit fidelity).
"""

import uuid
from typing import assert_never

from src.api.schemas.answer import (
    Answer,
    CitationWire,
    JurisdictionRefWire,
)
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.retrieval.evaluated_answer import (
    EvaluatedAnswer,
    NoEvaluation,
    NoEvaluationReason,
)
from src.domain.retrieval.item_verdict import (
    Accepted,
    Conflicted,
    ItemVerdict,
    NotCovered,
    Refused,
)


def verdict_to_short_answer(verdict: ItemVerdict) -> str:
    """Map an ItemVerdict to the wire short_answer tag.

    Contract-pinned per answer.md § Verdict mapping:
      Accepted (empty conditions)     -> 'yes'
      Accepted (non-empty conditions) -> 'conditional'
      Refused                         -> 'no'
      NotCovered                      -> 'unknown'
      Conflicted                      -> 'unknown'

    The assert_never arm makes basedpyright flag a missing arm at lint
    time when a new ItemVerdict variant is added without updating this
    function.
    """
    match verdict:
        case Accepted(conditions=conditions):
            return "conditional" if conditions else "yes"
        case Refused():
            return "no"
        case NotCovered():
            return "unknown"
        case Conflicted():
            return "unknown"
        case _ as unreachable:
            assert_never(unreachable)


def _refusal_reason_for_verdict(verdict: ItemVerdict) -> str | None:
    """Derive refusal_reason from ItemVerdict per answer.md invariants."""
    match verdict:
        case Accepted():
            return None
        case Refused():
            return None
        case NotCovered():
            return "no_evidence"
        case Conflicted():
            return "conflict_unresolved"
        case _ as unreachable:
            assert_never(unreachable)


def evaluated_answer_to_wire(
    answer: EvaluatedAnswer,
    audit_record_id: uuid.UUID,
    jurisdiction_id: JurisdictionId,
    jurisdiction_name: str,
) -> Answer:
    """Map an EvaluatedAnswer to the wire Answer shape."""
    short = verdict_to_short_answer(answer.verdict)
    refusal = _refusal_reason_for_verdict(answer.verdict)

    citations = [
        CitationWire(title=c.title, url=c.url, quote=c.quote)
        for c in answer.citations
    ]

    return Answer(
        audit_record_id=str(audit_record_id),
        short_answer=short,
        confidence=answer.confidence,
        recommended_action=answer.recommended_action,
        refusal_reason=refusal,
        clarifying_question=answer.clarifying_question,
        citations=citations,
        do_not_do=list(answer.do_not_do),
        preparation_steps=list(answer.preparation_steps),
        dropoff_options=[],
        jurisdiction=JurisdictionRefWire(
            id=str(jurisdiction_id.value),
            name=jurisdiction_name,
        ),
    )


def no_evaluation_to_wire(
    outcome: NoEvaluation,
    audit_record_id: uuid.UUID,
    location_input: str,
    jurisdiction_id: JurisdictionId | None = None,
    jurisdiction_name: str | None = None,
) -> Answer:
    """Map a NoEvaluation to the wire Answer shape.

    All NoEvaluation outcomes map to short_answer='unknown' (answer.md
    § Verdict mapping). The refusal_reason distinguishes OOJ from
    no_evidence cases.
    """
    reason = outcome.reason
    if reason == NoEvaluationReason.OUT_OF_JURISDICTION:
        refusal_reason: str | None = "out_of_jurisdiction"
        jurisdiction = JurisdictionRefWire(id=None, name=location_input)
    else:
        refusal_reason = "no_evidence"
        if jurisdiction_id is not None:
            jurisdiction = JurisdictionRefWire(
                id=str(jurisdiction_id.value),
                name=jurisdiction_name or "",
            )
        else:
            jurisdiction = JurisdictionRefWire(id=None, name=location_input)

    return Answer(
        audit_record_id=str(audit_record_id),
        short_answer="unknown",
        confidence="low",
        recommended_action=outcome.recommended_action,
        refusal_reason=refusal_reason,
        clarifying_question=outcome.clarifying_question,
        citations=[],
        do_not_do=[],
        preparation_steps=[],
        dropoff_options=[],
        jurisdiction=jurisdiction,
    )
