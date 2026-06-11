"""Tests for RetrievalService branches on the three NormalizationResult
variants. answer() receives an already-resolved Jurisdiction or None; the
service never calls location resolution itself.
"""

import uuid
from datetime import UTC, datetime
from typing import final

from src.domain.knowledge_base.jurisdiction import (
    Jurisdiction,
    JurisdictionId,
    JurisdictionType,
    SupportedStatus,
)
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
from src.domain.knowledge_base.rule import (
    AcceptedStatus,
    Disposition,
    Rule,
    RuleId,
)
from src.domain.knowledge_base.source import SourceDocument, SourceId
from src.domain.retrieval.citation import Citation
from src.domain.retrieval.evaluated_answer import (
    EvaluatedAnswer,
    NoEvaluation,
    NoEvaluationReason,
)
from src.domain.retrieval.item_verdict import Accepted
from src.domain.retrieval.location_resolver import DENVER_SLUG
from src.domain.retrieval.query import Query
from src.domain.retrieval.retrieval_llm import LLMMessage
from src.domain.retrieval.retrieval_service import RetrievalService


def _make_jurisdiction(slug: str = DENVER_SLUG) -> Jurisdiction:
    return Jurisdiction(
        id=JurisdictionId(uuid.uuid4()),
        name="City and County of Denver",
        slug=slug,
        type=JurisdictionType.CITY,
        country="US",
        supported_status=SupportedStatus.SUPPORTED,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )


def _make_material(slug: str) -> Material:
    return Material(
        id=MaterialId(uuid.uuid4()),
        canonical_name=slug.replace("-", " ").title(),
        slug=slug,
        category=MaterialCategory.PLASTIC,
    )


def _make_rule(
    jurisdiction_id: JurisdictionId,
    material_id: MaterialId,
    source_id: SourceId,
) -> Rule:
    return Rule(
        id=RuleId(uuid.uuid4()),
        jurisdiction_id=jurisdiction_id,
        material_id=material_id,
        disposition=Disposition.CURBSIDE_RECYCLE,
        accepted_status=AcceptedStatus.ACCEPTED,
        source_document_id=source_id,
        source_quote="Corrugated cardboard is accepted in purple recycle carts",
    )


def _make_source(source_id: SourceId, url: str) -> SourceDocument:
    return SourceDocument(
        id=source_id,
        jurisdiction_id=JurisdictionId(uuid.uuid4()),
        url=url,
        title="Denver Recycling Guidelines",
        authority_level=1,
        fetched_at=datetime.now(tz=UTC),
        source_text="...",
        source_text_hash="hash",
    )


@final
class _FakeNormalizer:
    """Returns a pre-set NormalizationResult variant."""

    def __init__(self, result: NormalizationResult) -> None:
        self._result = result

    def normalize(self, query_text: str) -> NormalizationResult:
        return self._result


class MemRuleRepo:
    """Configurable rule repo -- returns a pre-set rule list from find_for.

    Default is empty (forces the NO_EVIDENCE path). Other Protocol
    methods raise NotImplementedError because no test path needs them.
    """

    def __init__(self, rules: list[Rule] | None = None) -> None:
        self._rules: list[Rule] = rules or []

    def next_identity(self) -> RuleId:
        raise NotImplementedError("not exercised by these tests")

    def save(self, rule: Rule) -> None:
        raise NotImplementedError("not exercised by these tests")

    def find_by_id(self, rule_id: RuleId) -> Rule | None:
        raise NotImplementedError("not exercised by these tests")

    def find_for_jurisdiction(
        self,
        jurisdiction_id: JurisdictionId,
    ) -> list[Rule]:
        raise NotImplementedError("not exercised by these tests")

    def find_for(
        self,
        jurisdiction_id: JurisdictionId,
        material_id: MaterialId,
    ) -> list[Rule]:
        return list(self._rules)


class MemSourceRepo:
    """Dict-backed source repo. Unknown SourceIds return None."""

    def __init__(
        self, docs: dict[SourceId, SourceDocument] | None = None
    ) -> None:
        self._docs: dict[SourceId, SourceDocument] = docs or {}

    def next_identity(self) -> SourceId:
        raise NotImplementedError("not exercised by these tests")

    def save(self, source: SourceDocument) -> None:
        raise NotImplementedError("not exercised by these tests")

    def find_by_id(self, source_id: SourceId) -> SourceDocument | None:
        return self._docs.get(source_id)

    def find_for_jurisdiction(
        self,
        jurisdiction_id: JurisdictionId,
    ) -> list[SourceDocument]:
        raise NotImplementedError("not exercised by these tests")


@final
class _RecordingLLM:
    """Records call count; asserts pre-LLM branches never invoke it."""

    def __init__(self) -> None:
        self.call_count = 0

    def ask(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
    ):
        self.call_count += 1
        raise AssertionError(
            "RetrievalLLM must not be called on pre-LLM short-circuits"
        )


@final
class _ConfigurableLLM:
    """Returns a pre-set EvaluatedAnswer or NoEvaluation."""

    def __init__(self, response: EvaluatedAnswer | NoEvaluation) -> None:
        self._response = response

    def ask(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
    ) -> EvaluatedAnswer | NoEvaluation:
        return self._response


def _build_service(
    *,
    normalizer: _FakeNormalizer,
    rule_repo: MemRuleRepo | None = None,
    source_repo: MemSourceRepo | None = None,
    llm: _RecordingLLM | _ConfigurableLLM | None = None,
) -> RetrievalService:
    """Assemble RetrievalService with in-memory doubles."""
    return RetrievalService(
        material_normalizer=normalizer,  # type: ignore[arg-type]
        rule_repo=rule_repo or MemRuleRepo(),
        source_repo=source_repo or MemSourceRepo(),
        retrieval_llm=llm or _RecordingLLM(),  # type: ignore[arg-type]
    )


class TestOutOfJurisdiction:
    """A None jurisdiction short-circuits to OUT_OF_JURISDICTION before any
    material normalization or LLM call.
    """

    def test_none_jurisdiction_returns_ooj(self) -> None:
        llm = _RecordingLLM()
        service = _build_service(
            normalizer=_FakeNormalizer(Uncertain()),
            llm=llm,
        )

        result = service.answer(
            Query(text="cardboard", location_input="Aurora"), None
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.OUT_OF_JURISDICTION
        assert llm.call_count == 0


class TestAmbiguousMaterialPath:
    """`Ambiguous(candidates)` -> `NoEvaluation(reason=CONFLICTED)`."""

    def test_returns_no_evaluation_with_conflicted_reason(self) -> None:
        candidates = (_make_material("pet-bottle"), _make_material("hdpe-jug"))
        llm = _RecordingLLM()
        service = _build_service(
            normalizer=_FakeNormalizer(Ambiguous(candidates=candidates)),
            llm=llm,
        )

        result = service.answer(
            Query(text="plastic", location_input="Denver"),
            _make_jurisdiction(),
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.CONFLICTED
        assert result.clarifying_question is not None
        assert llm.call_count == 0


class TestUncertainMaterialPath:
    """`Uncertain` -> `NoEvaluation(reason=UNCERTAIN_MATERIAL)`."""

    def test_returns_no_evaluation_with_uncertain_reason(self) -> None:
        llm = _RecordingLLM()
        service = _build_service(
            normalizer=_FakeNormalizer(Uncertain()),
            llm=llm,
        )

        result = service.answer(
            Query(text="something obscure", location_input="Denver"),
            _make_jurisdiction(),
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
        service = _build_service(
            normalizer=_FakeNormalizer(Resolved(material=material)),
            llm=llm,
        )

        result = service.answer(
            Query(text="cardboard", location_input="Denver"),
            _make_jurisdiction(),
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.NO_EVIDENCE
        assert llm.call_count == 0


class TestRetrievedSourceUrlsFromRules:
    """retrieved_source_urls is built from each Rule's source_document_id
    via SourceRepo.find_by_id, then passed to the GroundingValidator.
    """

    def test_grounded_citation_url_returns_evaluated_answer(self) -> None:
        material = _make_material("cardboard")
        source_id = SourceId(uuid.uuid4())
        rule_url = "https://denvergov.org/recycling"

        denver = _make_jurisdiction()
        rule = _make_rule(denver.id, material.id, source_id)
        source = _make_source(source_id, rule_url)
        llm_answer = EvaluatedAnswer(
            verdict=Accepted(),
            citations=(Citation(title="Denver", url=rule_url),),
            recommended_action="Yes, recycle it.",
            confidence="high",
            retrieved_source_urls=frozenset(),
        )

        service = RetrievalService(
            material_normalizer=_FakeNormalizer(Resolved(material=material)),  # type: ignore[arg-type]
            rule_repo=MemRuleRepo(rules=[rule]),
            source_repo=MemSourceRepo(docs={source_id: source}),
            retrieval_llm=_ConfigurableLLM(llm_answer),  # type: ignore[arg-type]
        )

        result = service.answer(
            Query(text="cardboard", location_input="Denver"), denver
        )

        assert isinstance(result, EvaluatedAnswer)
        assert result.verdict == llm_answer.verdict
        assert result.citations == llm_answer.citations
        assert result.retrieved_source_urls == frozenset({rule_url})

    def test_ungrounded_citation_url_returns_validator_rejected(self) -> None:
        material = _make_material("cardboard")
        source_id = SourceId(uuid.uuid4())

        denver = _make_jurisdiction()
        rule = _make_rule(denver.id, material.id, source_id)
        source = _make_source(source_id, "https://denvergov.org/recycling")
        llm_answer = EvaluatedAnswer(
            verdict=Accepted(),
            citations=(
                Citation(title="Hallucination", url="https://made-up.example"),
            ),
            recommended_action="Yes.",
            confidence="high",
            retrieved_source_urls=frozenset(),
        )

        service = RetrievalService(
            material_normalizer=_FakeNormalizer(Resolved(material=material)),  # type: ignore[arg-type]
            rule_repo=MemRuleRepo(rules=[rule]),
            source_repo=MemSourceRepo(docs={source_id: source}),
            retrieval_llm=_ConfigurableLLM(llm_answer),  # type: ignore[arg-type]
        )

        result = service.answer(
            Query(text="cardboard", location_input="Denver"), denver
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.VALIDATOR_REJECTED

    def test_multiple_sources_returns_full_retrieved_set(self) -> None:
        material = _make_material("cardboard")
        sid_a, sid_b = SourceId(uuid.uuid4()), SourceId(uuid.uuid4())
        url_a = "https://denvergov.org/recycling"
        url_b = "https://denvergov.org/guidelines"

        denver = _make_jurisdiction()
        rules = [
            _make_rule(denver.id, material.id, sid_a),
            _make_rule(denver.id, material.id, sid_b),
        ]
        llm_answer = EvaluatedAnswer(
            verdict=Accepted(),
            citations=(Citation(title="B", url=url_b),),
            recommended_action="Yes.",
            confidence="high",
            retrieved_source_urls=frozenset(),
        )

        service = RetrievalService(
            material_normalizer=_FakeNormalizer(Resolved(material=material)),  # type: ignore[arg-type]
            rule_repo=MemRuleRepo(rules=rules),
            source_repo=MemSourceRepo(
                docs={
                    sid_a: _make_source(sid_a, url_a),
                    sid_b: _make_source(sid_b, url_b),
                }
            ),
            retrieval_llm=_ConfigurableLLM(llm_answer),  # type: ignore[arg-type]
        )

        result = service.answer(
            Query(text="cardboard", location_input="Denver"), denver
        )

        assert isinstance(result, EvaluatedAnswer)
        assert result.retrieved_source_urls == frozenset({url_a, url_b})

    def test_partial_source_repo_miss_excludes_missing_url(self) -> None:
        material = _make_material("cardboard")
        sid_found = SourceId(uuid.uuid4())
        sid_missing = SourceId(uuid.uuid4())
        found_url = "https://denvergov.org/recycling"
        missing_url = "https://denvergov.org/not-in-repo"

        denver = _make_jurisdiction()
        rules = [
            _make_rule(denver.id, material.id, sid_found),
            _make_rule(denver.id, material.id, sid_missing),
        ]
        llm_answer = EvaluatedAnswer(
            verdict=Accepted(),
            citations=(Citation(title="Missing", url=missing_url),),
            recommended_action="Yes.",
            confidence="high",
            retrieved_source_urls=frozenset(),
        )

        service = RetrievalService(
            material_normalizer=_FakeNormalizer(Resolved(material=material)),  # type: ignore[arg-type]
            rule_repo=MemRuleRepo(rules=rules),
            source_repo=MemSourceRepo(
                docs={sid_found: _make_source(sid_found, found_url)}
            ),
            retrieval_llm=_ConfigurableLLM(llm_answer),  # type: ignore[arg-type]
        )

        result = service.answer(
            Query(text="cardboard", location_input="Denver"), denver
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.VALIDATOR_REJECTED

    def test_source_repo_miss_excludes_url_from_set(self) -> None:
        """A Rule whose source_document_id has no SourceDocument in the
        repo contributes no URL to retrieved_source_urls. The LLM that
        cites a URL not in the set should be rejected.
        """
        material = _make_material("cardboard")
        source_id = SourceId(uuid.uuid4())

        denver = _make_jurisdiction()
        rule = _make_rule(denver.id, material.id, source_id)
        llm_answer = EvaluatedAnswer(
            verdict=Accepted(),
            citations=(
                Citation(title="X", url="https://denvergov.org/recycling"),
            ),
            recommended_action="Yes.",
            confidence="high",
            retrieved_source_urls=frozenset(),
        )

        service = RetrievalService(
            material_normalizer=_FakeNormalizer(Resolved(material=material)),  # type: ignore[arg-type]
            rule_repo=MemRuleRepo(rules=[rule]),
            source_repo=MemSourceRepo(docs={}),
            retrieval_llm=_ConfigurableLLM(llm_answer),  # type: ignore[arg-type]
        )

        result = service.answer(
            Query(text="cardboard", location_input="Denver"), denver
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.VALIDATOR_REJECTED


class TestFallbackForValidatorRejection:
    """`fallback_for_validator_rejection` returns the spec-pinned outcome."""

    def test_returns_validator_rejected_no_evaluation(self) -> None:
        """fallback_for_validator_rejection() returns
        NoEvaluation(reason=VALIDATOR_REJECTED) with a non-empty
        recommended_action matching the spec-pinned grounding-failure text.
        """
        service = _build_service(
            normalizer=_FakeNormalizer(Uncertain()),
        )
        query = Query(text="cardboard", location_input="Denver")

        result = service.fallback_for_validator_rejection(query)

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.VALIDATOR_REJECTED
        assert "grounded" in result.recommended_action.lower()
