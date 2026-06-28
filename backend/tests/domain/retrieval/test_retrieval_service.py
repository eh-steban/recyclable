"""Tests for RetrievalService branches on the three NormalizationResult
variants. answer() receives an already-resolved Jurisdiction or None; the
service never calls location resolution itself.
"""

import uuid

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.material import MaterialId
from src.domain.knowledge_base.normalization_result import (
    Ambiguous,
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
from src.domain.retrieval.query import Query
from src.domain.retrieval.retrieval_service import RetrievalService
from tests.utils.builders import (
    make_jurisdiction,
    make_material,
    make_rule,
    make_source_document,
)
from tests.utils.fakes.anthropic_client import FakeAnthropicClient
from tests.utils.fakes.llm import NeverCalledLLM, StubNormalizer


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


def _build_service(
    *,
    normalizer: StubNormalizer,
    rule_repo: MemRuleRepo | None = None,
    source_repo: MemSourceRepo | None = None,
    llm: NeverCalledLLM | FakeAnthropicClient | None = None,
) -> RetrievalService:
    return RetrievalService(
        material_normalizer=normalizer,  # type: ignore[arg-type]
        rule_repo=rule_repo or MemRuleRepo(),
        source_repo=source_repo or MemSourceRepo(),
        retrieval_llm=llm or NeverCalledLLM(),  # type: ignore[arg-type]
    )


class TestOutOfJurisdiction:
    """A None jurisdiction short-circuits to OUT_OF_JURISDICTION before any
    material normalization or LLM call.
    """

    def test_none_jurisdiction_returns_ooj(self) -> None:
        llm = NeverCalledLLM()
        service = _build_service(
            normalizer=StubNormalizer(Uncertain()),
            llm=llm,
        )

        result = service.answer(
            Query(text="cardboard", location_input="Aurora"), None
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.OUT_OF_JURISDICTION
        assert llm.call_count == 0


class TestAmbiguousMaterialPath:
    def test_returns_no_evaluation_with_ambiguous_material_reason(self) -> None:
        candidates = (
            make_material(slug="pet-bottle"),
            make_material(slug="hdpe-jug"),
        )
        llm = NeverCalledLLM()
        service = _build_service(
            normalizer=StubNormalizer(Ambiguous(candidates=candidates)),
            llm=llm,
        )

        result = service.answer(
            Query(text="plastic", location_input="Denver"),
            make_jurisdiction(),
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.AMBIGUOUS_MATERIAL
        assert result.clarifying_question is not None
        assert llm.call_count == 0


class TestUncertainMaterialPath:
    def test_returns_no_evaluation_with_uncertain_reason(self) -> None:
        llm = NeverCalledLLM()
        service = _build_service(
            normalizer=StubNormalizer(Uncertain()),
            llm=llm,
        )

        result = service.answer(
            Query(text="something obscure", location_input="Denver"),
            make_jurisdiction(),
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.UNCERTAIN_MATERIAL
        assert result.clarifying_question is not None
        assert llm.call_count == 0


class TestResolvedMaterialReachesRetrievalStep:
    def test_resolved_proceeds_past_normalizer_step(self) -> None:
        material = make_material(slug="cardboard")
        llm = NeverCalledLLM()
        service = _build_service(
            normalizer=StubNormalizer(Resolved(material=material)),
            llm=llm,
        )

        result = service.answer(
            Query(text="cardboard", location_input="Denver"),
            make_jurisdiction(),
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.NO_EVIDENCE
        assert llm.call_count == 0


class TestRetrievedSourceUrlsFromRules:
    """retrieved_source_urls is built from each Rule's source_document_id
    via SourceRepo.find_by_id, then passed to the GroundingValidator.
    """

    def test_grounded_citation_url_returns_evaluated_answer(self) -> None:
        material = make_material(slug="cardboard")
        source_id = SourceId(uuid.uuid4())
        rule_url = "https://denvergov.org/recycling"

        denver = make_jurisdiction()
        rule = make_rule(
            jurisdiction_id=denver.id,
            material_id=material.id,
            source_document_id=source_id,
        )
        source = make_source_document(id=source_id, url=rule_url)
        llm_answer = EvaluatedAnswer(
            verdict=Accepted(
                citations=(Citation(title="Denver", url=rule_url),)
            ),
            recommended_action="Yes, recycle it.",
            confidence="high",
            retrieved_source_urls=frozenset(),
        )

        service = RetrievalService(
            material_normalizer=StubNormalizer(Resolved(material=material)),  # type: ignore[arg-type]
            rule_repo=MemRuleRepo(rules=[rule]),
            source_repo=MemSourceRepo(docs={source_id: source}),
            retrieval_llm=FakeAnthropicClient(ask_result=llm_answer),  # type: ignore[arg-type]
        )

        result = service.answer(
            Query(text="cardboard", location_input="Denver"), denver
        )

        assert isinstance(result, EvaluatedAnswer)
        assert result.verdict == llm_answer.verdict
        assert result.retrieved_source_urls == frozenset({rule_url})

    def test_ungrounded_citation_url_returns_validator_rejected(self) -> None:
        material = make_material(slug="cardboard")
        source_id = SourceId(uuid.uuid4())

        denver = make_jurisdiction()
        rule = make_rule(
            jurisdiction_id=denver.id,
            material_id=material.id,
            source_document_id=source_id,
        )
        source = make_source_document(
            id=source_id, url="https://denvergov.org/recycling"
        )
        llm_answer = EvaluatedAnswer(
            verdict=Accepted(
                citations=(
                    Citation(
                        title="Hallucination", url="https://made-up.example"
                    ),
                )
            ),
            recommended_action="Yes.",
            confidence="high",
            retrieved_source_urls=frozenset(),
        )

        service = RetrievalService(
            material_normalizer=StubNormalizer(Resolved(material=material)),  # type: ignore[arg-type]
            rule_repo=MemRuleRepo(rules=[rule]),
            source_repo=MemSourceRepo(docs={source_id: source}),
            retrieval_llm=FakeAnthropicClient(ask_result=llm_answer),  # type: ignore[arg-type]
        )

        result = service.answer(
            Query(text="cardboard", location_input="Denver"), denver
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.VALIDATOR_REJECTED

    def test_multiple_sources_returns_full_retrieved_set(self) -> None:
        material = make_material(slug="cardboard")
        sid_a, sid_b = SourceId(uuid.uuid4()), SourceId(uuid.uuid4())
        url_a = "https://denvergov.org/recycling"
        url_b = "https://denvergov.org/guidelines"

        denver = make_jurisdiction()
        rules = [
            make_rule(
                jurisdiction_id=denver.id,
                material_id=material.id,
                source_document_id=sid_a,
            ),
            make_rule(
                jurisdiction_id=denver.id,
                material_id=material.id,
                source_document_id=sid_b,
            ),
        ]
        llm_answer = EvaluatedAnswer(
            verdict=Accepted(citations=(Citation(title="B", url=url_b),)),
            recommended_action="Yes.",
            confidence="high",
            retrieved_source_urls=frozenset(),
        )

        service = RetrievalService(
            material_normalizer=StubNormalizer(Resolved(material=material)),  # type: ignore[arg-type]
            rule_repo=MemRuleRepo(rules=rules),
            source_repo=MemSourceRepo(
                docs={
                    sid_a: make_source_document(id=sid_a, url=url_a),
                    sid_b: make_source_document(id=sid_b, url=url_b),
                }
            ),
            retrieval_llm=FakeAnthropicClient(ask_result=llm_answer),  # type: ignore[arg-type]
        )

        result = service.answer(
            Query(text="cardboard", location_input="Denver"), denver
        )

        assert isinstance(result, EvaluatedAnswer)
        assert result.retrieved_source_urls == frozenset({url_a, url_b})

    def test_partial_source_repo_miss_excludes_missing_url(self) -> None:
        material = make_material(slug="cardboard")
        sid_found = SourceId(uuid.uuid4())
        sid_missing = SourceId(uuid.uuid4())
        found_url = "https://denvergov.org/recycling"
        missing_url = "https://denvergov.org/not-in-repo"

        denver = make_jurisdiction()
        rules = [
            make_rule(
                jurisdiction_id=denver.id,
                material_id=material.id,
                source_document_id=sid_found,
            ),
            make_rule(
                jurisdiction_id=denver.id,
                material_id=material.id,
                source_document_id=sid_missing,
            ),
        ]
        llm_answer = EvaluatedAnswer(
            verdict=Accepted(
                citations=(Citation(title="Missing", url=missing_url),)
            ),
            recommended_action="Yes.",
            confidence="high",
            retrieved_source_urls=frozenset(),
        )

        service = RetrievalService(
            material_normalizer=StubNormalizer(Resolved(material=material)),  # type: ignore[arg-type]
            rule_repo=MemRuleRepo(rules=rules),
            source_repo=MemSourceRepo(
                docs={
                    sid_found: make_source_document(id=sid_found, url=found_url)
                }
            ),
            retrieval_llm=FakeAnthropicClient(ask_result=llm_answer),  # type: ignore[arg-type]
        )

        result = service.answer(
            Query(text="cardboard", location_input="Denver"), denver
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.VALIDATOR_REJECTED

    def test_source_repo_miss_excludes_url_from_set(self) -> None:
        material = make_material(slug="cardboard")
        source_id = SourceId(uuid.uuid4())

        denver = make_jurisdiction()
        rule = make_rule(
            jurisdiction_id=denver.id,
            material_id=material.id,
            source_document_id=source_id,
        )
        llm_answer = EvaluatedAnswer(
            verdict=Accepted(
                citations=(
                    Citation(title="X", url="https://denvergov.org/recycling"),
                )
            ),
            recommended_action="Yes.",
            confidence="high",
            retrieved_source_urls=frozenset(),
        )

        service = RetrievalService(
            material_normalizer=StubNormalizer(Resolved(material=material)),  # type: ignore[arg-type]
            rule_repo=MemRuleRepo(rules=[rule]),
            source_repo=MemSourceRepo(docs={}),
            retrieval_llm=FakeAnthropicClient(ask_result=llm_answer),  # type: ignore[arg-type]
        )

        result = service.answer(
            Query(text="cardboard", location_input="Denver"), denver
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.VALIDATOR_REJECTED


class TestUnknownStatusRule:
    """A retrieved rule with accepted_status=UNKNOWN short-circuits to
    NO_EVIDENCE before the LLM -- it states no disposition, so sending it
    to the model would force a guessed (yet citable) verdict.
    """

    def test_unknown_status_returns_no_evidence_without_llm(self) -> None:
        material = make_material(slug="mystery-plastic")
        source_id = SourceId(uuid.uuid4())
        denver = make_jurisdiction()
        rule = make_rule(
            jurisdiction_id=denver.id,
            material_id=material.id,
            source_document_id=source_id,
            disposition=Disposition.UNKNOWN,
            accepted_status=AcceptedStatus.UNKNOWN,
            source_quote="Status of this material is under review.",
        )
        source = make_source_document(
            id=source_id, url="https://denvergov.org/recycling"
        )
        llm = NeverCalledLLM()

        service = _build_service(
            normalizer=StubNormalizer(Resolved(material=material)),
            rule_repo=MemRuleRepo(rules=[rule]),
            source_repo=MemSourceRepo(docs={source_id: source}),
            llm=llm,
        )

        result = service.answer(
            Query(text="mystery plastic", location_input="Denver"), denver
        )

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.NO_EVIDENCE
        assert llm.call_count == 0


class TestFallbackForValidatorRejection:
    """`fallback_for_validator_rejection` returns the spec-pinned outcome."""

    def test_returns_validator_rejected_no_evaluation(self) -> None:
        service = _build_service(
            normalizer=StubNormalizer(Uncertain()),
        )
        query = Query(text="cardboard", location_input="Denver")

        result = service.fallback_for_validator_rejection(query)

        assert isinstance(result, NoEvaluation)
        assert result.reason == NoEvaluationReason.VALIDATOR_REJECTED
        assert "grounded" in result.recommended_action.lower()
