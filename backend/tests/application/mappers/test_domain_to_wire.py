"""Wire-mapper enforcement of the recommended_action length cap.

answer.md guarantees <= 500 chars on the wire; the domain -> wire
mapper enforces the cap independently of any model cooperation.
"""

import uuid

from src.application.mappers.domain_to_wire import (
    evaluated_answer_to_wire,
    no_evaluation_to_wire,
)
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.retrieval.citation import Citation
from src.domain.retrieval.evaluated_answer import (
    EvaluatedAnswer,
    NoEvaluation,
    NoEvaluationReason,
)
from src.domain.retrieval.item_verdict import Accepted

_CAP = 500


def _evaluated(
    recommended_action: str, confidence: str = "high"
) -> EvaluatedAnswer:
    return EvaluatedAnswer(
        verdict=Accepted(
            citations=(Citation(title="Denver", url="https://denver.gov"),)
        ),
        recommended_action=recommended_action,
        confidence=confidence,
        retrieved_source_urls=frozenset({"https://denver.gov"}),
    )


def _to_wire(answer: EvaluatedAnswer):
    return evaluated_answer_to_wire(
        answer,
        audit_record_id=uuid.uuid4(),
        jurisdiction_id=JurisdictionId(uuid.uuid4()),
        jurisdiction_name="Denver",
    )


def test_recommended_action_within_cap_passes_through() -> None:
    text = "Rinse and place in the purple cart."
    result = _to_wire(_evaluated(text))
    assert result.recommended_action == text


def test_recommended_action_at_cap_passes_through() -> None:
    text = "x" * _CAP
    result = _to_wire(_evaluated(text))
    assert result.recommended_action == text


def test_recommended_action_over_cap_drops_partial_trailing_word() -> None:
    text = "alpha " * 100  # 600 chars; the cap falls mid-"alpha"
    result = _to_wire(_evaluated(text))
    action = result.recommended_action
    assert len(action) <= _CAP
    assert text.startswith(action)
    assert action == action.rstrip()  # no dangling whitespace
    assert action.split()[-1] == "alpha"  # ends on a whole word


def test_recommended_action_no_whitespace_hard_cut() -> None:
    text = "x" * 600
    result = _to_wire(_evaluated(text))
    assert result.recommended_action == "x" * _CAP


def test_recommended_action_leading_whitespace_long_token_not_emptied() -> None:
    # A leading space before a single long token has no interior word
    # boundary; the cap must hard-cut, never zero the field.
    text = " " + "x" * 600
    result = _to_wire(_evaluated(text))
    action = result.recommended_action
    assert action  # non-empty -- the field is not silently dropped
    assert len(action) <= _CAP
    assert "x" in action


def test_truncation_does_not_touch_confidence() -> None:
    result = _to_wire(_evaluated("alpha " * 100, confidence="high"))
    assert result.confidence == "high"


def test_no_evaluation_recommended_action_is_capped() -> None:
    text = "alpha " * 100
    outcome = NoEvaluation(
        reason=NoEvaluationReason.NO_EVIDENCE,
        recommended_action=text,
    )
    result = no_evaluation_to_wire(
        outcome,
        audit_record_id=uuid.uuid4(),
        location_input="Denver, CO",
    )
    action = result.recommended_action
    assert len(action) <= _CAP
    assert text.startswith(action)  # content preserved, not replaced
    assert result.confidence == "low"  # refusal confidence stays pinned
    assert result.short_answer == "unknown"
