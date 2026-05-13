"""EvaluatedAnswer and NoEvaluation Values.

These are the two top-level outcomes of the RetrievalService.
The application layer maps them to the wire Answer shape.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from src.domain.retrieval.citation import Citation
from src.domain.retrieval.item_verdict import ItemVerdict

# ---------------------------------------------------------------------------
# EvaluatedAnswer -- LLM produced a grounded verdict
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EvaluatedAnswer:
    """A grounded answer produced by the LLM and validated.

    verdict: the domain verdict (Accepted | Refused | NotCovered | Conflicted).
    citations: sources that support the verdict. Non-empty for definitive
               verdicts per INV-PROD-001.
    recommended_action: short actionable text (<= 200 characters on wire).
    clarifying_question: non-None when material normalization was ambiguous.
    """

    verdict: ItemVerdict
    citations: tuple[Citation, ...]
    recommended_action: str
    confidence: str  # 'high' | 'medium' | 'low'
    preparation_steps: tuple[str, ...] = field(default_factory=tuple)
    do_not_do: tuple[str, ...] = field(default_factory=tuple)
    clarifying_question: str | None = None


# ---------------------------------------------------------------------------
# NoEvaluation -- retrieval refused before or after LLM call
# ---------------------------------------------------------------------------


class NoEvaluationReason(StrEnum):
    """Reason the retrieval service could not produce an evaluated answer."""

    OUT_OF_JURISDICTION = "out_of_jurisdiction"
    NO_EVIDENCE = "no_evidence"
    VALIDATOR_REJECTED = "validator_rejected"


@dataclass(frozen=True, slots=True)
class NoEvaluation:
    """The retrieval service refused to evaluate this query.

    reason explains why:
    - OutOfJurisdiction: location not in the supported alias set.
    - NoEvidence: no rule found for (jurisdiction, material).
    - ValidatorRejected: GroundingValidator hard-blocked the LLM response.
    """

    reason: NoEvaluationReason
    recommended_action: str = ""
