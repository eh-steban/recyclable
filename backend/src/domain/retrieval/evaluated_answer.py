"""EvaluatedAnswer and NoEvaluation Values.

These are the two top-level outcomes of the RetrievalService.
The application layer maps them to the wire Answer shape.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from src.domain.retrieval.item_verdict import ItemVerdict

# ---------------------------------------------------------------------------
# EvaluatedAnswer -- LLM produced a grounded verdict
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EvaluatedAnswer:
    """A grounded answer produced by the LLM and validated.

    verdict: the domain verdict (Accepted | Refused | NotCovered | Conflicted).
             Citations are carried by the verdict itself (INV-PROD-001).
    recommended_action: short actionable text (<= 500 characters on wire).
    retrieved_source_urls: the grounding allow-list (INV-LLM-002) -- the URL
               set behind the retrieved rules, of which citations must be a
               subset.
    clarifying_question: non-None when material normalization was ambiguous.
    """

    verdict: ItemVerdict
    recommended_action: str
    confidence: str  # 'high' | 'medium' | 'low'
    retrieved_source_urls: frozenset[str]
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
    LLM_REJECTED = "llm_rejected"
    UNCERTAIN_MATERIAL = "uncertain_material"
    AMBIGUOUS_MATERIAL = "ambiguous_material"


@dataclass(frozen=True, slots=True)
class NoEvaluation:
    """The retrieval service refused to evaluate this query.

    reason explains why:
    - OUT_OF_JURISDICTION: location not in the supported alias set.
    - NO_EVIDENCE: no actionable rule for (jurisdiction, material) --
      either no current rule exists, or the only current rule has
      accepted_status UNKNOWN (states no disposition, so it cannot ground
      a verdict). Both reach the user as "unknown".
    - VALIDATOR_REJECTED: model answered, but GroundingValidator
      hard-blocked the response (parse failure, schema mismatch, or
      grounding-citation violation). The model produced output.
    - LLM_REJECTED: the Sonnet call itself failed -- timeout, network
      error, 4xx/5xx after retry exhaustion. No model output to validate.
      Per INV-PROD-004, this reason -- not VALIDATOR_REJECTED -- is the
      correct domain shape for Anthropic unavailability.
    - UNCERTAIN_MATERIAL: normalizer could not classify the material.
    - AMBIGUOUS_MATERIAL: normalizer matched multiple candidate materials.
      (Distinct from the rule-level `Conflicted` ItemVerdict, which means
      sources disagree on a retrieved rule -- a different layer, surfaced
      by ingestion, not this reason.)

    `clarifying_question` is set on the material-level paths
    (UNCERTAIN_MATERIAL, AMBIGUOUS_MATERIAL) so the UI can ask the user to
    pick or rephrase. Other reasons leave it None.
    """

    reason: NoEvaluationReason
    recommended_action: str = ""
    clarifying_question: str | None = None
