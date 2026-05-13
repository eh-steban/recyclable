"""Tests for RetrievalService branches on the three NormalizationResult
variants.
"""

import uuid
from typing import final

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.material import (
    Material,
    MaterialCategory,
    MaterialId,
)
from src.domain.knowledge_base.normalization_result import (
    Ambiguous,
    NormalizationResult,
    Resolved,
    Uncertain,
)
from src.domain.knowledge_base.rule import Rule, RuleId
from src.domain.retrieval.evaluated_answer import (
    NoEvaluation,
    NoEvaluationReason,
)
from src.domain.retrieval.query import Query
from src.domain.retrieval.retrieval_llm import LLMMessage
from src.domain.retrieval.retrieval_service import RetrievalService


def _make_material(slug: str) -> Material:
    return Material(
        id=MaterialId(uuid.uuid4()),
        canonical_name=slug.replace("-", " ").title(),
        slug=slug,
        category=MaterialCategory.PLASTIC,
    )


@final
class _FakeNormalizer:
    """Returns a pre-set NormalizationResult variant."""

    def __init__(self, result: NormalizationResult) -> None:
        self._result = result

    def normalize(self, query_text: str) -> NormalizationResult:  # pyright: ignore[reportUnusedParameter]
        return self._result


class _FakeRuleRepo:
    """No-rule repo -- forces the NO_EVIDENCE path on Resolved tests.

    Implements the full RuleRepo Protocol; methods other than find_for
    raise NotImplementedError because the pre-LLM short-circuit tests
    never reach them.
    """

    def next_identity(self) -> RuleId:
        raise NotImplementedError(
            "not exercised in pre-LLM short-circuit tests"
        )

    def save(self, rule: Rule) -> None:  # pyright: ignore[reportUnusedParameter]
        raise NotImplementedError(
            "not exercised in pre-LLM short-circuit tests"
        )

    def find_by_id(self, rule_id: RuleId) -> Rule | None:  # pyright: ignore[reportUnusedParameter]
        raise NotImplementedError(
            "not exercised in pre-LLM short-circuit tests"
        )

    def find_for(
        self,
        jurisdiction_id: JurisdictionId,  # pyright: ignore[reportUnusedParameter]
        material_id: MaterialId,  # pyright: ignore[reportUnusedParameter]
    ) -> list[Rule]:
        return []


@final
class _RecordingLLM:
    """Records call count; asserts pre-LLM branches never invoke it."""

    def __init__(self) -> None:
        self.call_count = 0

    def ask(
        self,
        messages: list[LLMMessage],  # pyright: ignore[reportUnusedParameter]
        system_prompt: str,  # pyright: ignore[reportUnusedParameter]
    ):
        self.call_count += 1
        raise AssertionError(
            "RetrievalLLM must not be called on pre-LLM short-circuits"
        )


class TestAmbiguousMaterialPath:
    """`Ambiguous(candidates)` -> `NoEvaluation(reason=CONFLICTED)`."""

    def test_returns_no_evaluation_with_conflicted_reason(self) -> None:
        candidates = (_make_material("pet-bottle"), _make_material("hdpe-jug"))
        llm = _RecordingLLM()
        service = RetrievalService(
            material_normalizer=_FakeNormalizer(
                Ambiguous(candidates=candidates)
            ),
            rule_repository=_FakeRuleRepo(),
            retrieval_llm=llm,
        )

        result = service.answer(Query(text="plastic", location_input="Denver"))

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.CONFLICTED
        assert result.clarifying_question is not None
        assert llm.call_count == 0


class TestUncertainMaterialPath:
    """`Uncertain` -> `NoEvaluation(reason=UNCERTAIN_MATERIAL)`."""

    def test_returns_no_evaluation_with_uncertain_reason(self) -> None:
        llm = _RecordingLLM()
        service = RetrievalService(
            material_normalizer=_FakeNormalizer(Uncertain()),
            rule_repository=_FakeRuleRepo(),
            retrieval_llm=llm,
        )

        result = service.answer(
            Query(text="something obscure", location_input="Denver")
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.UNCERTAIN_MATERIAL
        assert result.clarifying_question is not None
        assert llm.call_count == 0


class TestResolvedMaterialReachesRetrievalStep:
    """`Resolved` must NOT short-circuit -- flows into rule retrieval."""

    def test_resolved_proceeds_past_normalizer_step(self) -> None:
        material = _make_material("cardboard")
        llm = _RecordingLLM()
        service = RetrievalService(
            material_normalizer=_FakeNormalizer(Resolved(material=material)),
            rule_repository=_FakeRuleRepo(),
            retrieval_llm=llm,
        )

        result = service.answer(
            Query(text="cardboard", location_input="Denver")
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.NO_EVIDENCE
        assert llm.call_count == 0
