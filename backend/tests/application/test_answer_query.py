"""Application-service tests for AnswerQuery.

Uses in-memory port doubles (no Postgres, no Anthropic).
Covers: happy path, OOJ, ambiguous/uncertain material,
validator-rejected, save-failure, LLM-rejected,
ItemVerdict sum-completeness, and SEO-page paths.
"""

import uuid
from datetime import UTC, datetime
from typing import final, get_args

import pytest

from src.application.answer_query import AnswerQuery, _make_record
from src.application.answer_query_command import AnswerQueryCommand
from src.application.get_jurisdiction_page import GetJurisdictionPage
from src.application.mappers.domain_to_wire import (
    evaluated_answer_to_wire,
    no_evaluation_to_wire,
    verdict_to_short_answer,
)
from src.domain.audit.answer_audit_record import AnswerAuditRecordId
from src.domain.exceptions import AnswerAuditRecordValidationError
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
from src.domain.retrieval.item_verdict import (
    Accepted,
    Conflicted,
    ItemVerdict,
    NotCovered,
)
from src.domain.retrieval.location_resolver import DENVER_SLUG
from src.domain.retrieval.query import Query
from src.domain.retrieval.retrieval_llm import LLMMessage
from src.domain.retrieval.retrieval_service import RetrievalService
from tests._fakes.answer_audit_record_repo import MemAnswerAuditRecordRepo
from tests._fakes.jurisdiction_repo import MemJurisdictionRepo
from tests._fakes.material_repo import MemMaterialRepo
from tests._fakes.rule_repo import MemRuleRepo
from tests._fakes.source_repo import MemSourceRepo

# ---------------------------------------------------------------------------
# Fake LLM implementations
# ---------------------------------------------------------------------------


@final
class _FakeLLM:
    def __init__(self, result: EvaluatedAnswer | NoEvaluation) -> None:
        self._result = result
        self.call_count = 0

    def ask(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
    ) -> EvaluatedAnswer | NoEvaluation:
        self.call_count += 1
        return self._result


@final
class _NeverCalledLLM:
    def ask(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
    ) -> EvaluatedAnswer | NoEvaluation:
        raise AssertionError("LLM should not be called on this path")


# ---------------------------------------------------------------------------
# Fake normalizer
# ---------------------------------------------------------------------------


@final
class _FakeNormalizer:
    def __init__(self, result: NormalizationResult) -> None:
        self._result = result

    def normalize(self, query_text: str) -> NormalizationResult:
        return self._result


# ---------------------------------------------------------------------------
# Fake RetrievalService (bypasses GroundingValidator)
# ---------------------------------------------------------------------------


@final
class _FakeRetrievalService:
    """Used to exercise the construction-time validator fallback path
    (the path that only fires when the GroundingValidator is bypassed).
    """

    def __init__(
        self,
        answer_result: EvaluatedAnswer | NoEvaluation,
    ) -> None:
        self._answer_result = answer_result

    def answer(
        self, query: Query, jurisdiction: Jurisdiction | None
    ) -> EvaluatedAnswer | NoEvaluation:
        return self._answer_result

    def fallback_for_validator_rejection(self, query: Query) -> NoEvaluation:
        return NoEvaluation(
            reason=NoEvaluationReason.VALIDATOR_REJECTED,
            recommended_action=(
                "The answer could not be grounded in the retrieved sources."
            ),
        )


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------


def _make_jurisdiction_id() -> JurisdictionId:
    return JurisdictionId(uuid.uuid4())


def _make_denver_jurisdiction() -> Jurisdiction:
    return Jurisdiction(
        id=JurisdictionId(uuid.uuid4()),
        name="City and County of Denver",
        slug=DENVER_SLUG,
        type=JurisdictionType.CITY,
        country="US",
        supported_status=SupportedStatus.SUPPORTED,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )


def _make_material(slug: str = "cardboard") -> Material:
    return Material(
        id=MaterialId(uuid.uuid4()),
        canonical_name=slug.replace("-", " ").title(),
        slug=slug,
        category=MaterialCategory.PAPER,
    )


def _make_rule(
    jid: JurisdictionId,
    mid: MaterialId,
    sid: SourceId,
    preparation_steps: tuple[str, ...] = (),
) -> Rule:
    return Rule(
        id=RuleId(uuid.uuid4()),
        jurisdiction_id=jid,
        material_id=mid,
        disposition=Disposition.CURBSIDE_RECYCLE,
        accepted_status=AcceptedStatus.ACCEPTED,
        source_document_id=sid,
        source_quote="Cardboard is accepted curbside.",
        preparation_steps=preparation_steps,
    )


def _make_evaluated_answer(
    verdict: ItemVerdict,
    citations: tuple[Citation, ...],
    recommended_action: str = "Place in the blue bin.",
    retrieved_source_urls: frozenset[str] = frozenset(),
) -> EvaluatedAnswer:
    return EvaluatedAnswer(
        verdict=verdict,
        citations=citations,
        recommended_action=recommended_action,
        confidence="high",
        retrieved_source_urls=retrieved_source_urls,
    )


def _make_citation(url: str) -> Citation:
    return Citation(
        title="Denver Recycling Guide",
        url=url,
        quote="Cardboard is accepted curbside.",
    )


def _build_service(
    *,
    normalizer: _FakeNormalizer | None = None,
    llm: _FakeLLM | _NeverCalledLLM | None = None,
    rule_repo: MemRuleRepo | None = None,
    source_repo: MemSourceRepo | None = None,
    audit_repo: MemAnswerAuditRecordRepo | None = None,
    jurisdiction: Jurisdiction | None = None,
) -> tuple[
    AnswerQuery,
    MemAnswerAuditRecordRepo,
    Jurisdiction,
]:
    """Assemble AnswerQuery with overridable doubles.

    Returns (svc, audit_repo, denver_jurisdiction) so callers can assert
    on the jurisdiction's generated id.
    """
    _rule_repo = rule_repo or MemRuleRepo()
    _source_repo = source_repo or MemSourceRepo()
    _audit_repo = audit_repo or MemAnswerAuditRecordRepo()

    _llm: _FakeLLM | _NeverCalledLLM = llm or _NeverCalledLLM()
    _normalizer = normalizer or _FakeNormalizer(Uncertain())

    # Seed a generated-UUID Denver jurisdiction in the in-memory repo.
    _jurisdiction = jurisdiction or _make_denver_jurisdiction()
    j_repo = MemJurisdictionRepo()
    j_repo.save(_jurisdiction)

    retrieval_svc = RetrievalService(
        material_normalizer=_normalizer,  # type: ignore[arg-type]
        rule_repo=_rule_repo,
        source_repo=_source_repo,
        retrieval_llm=_llm,  # type: ignore[arg-type]
    )
    svc = AnswerQuery(
        retrieval_service=retrieval_svc,
        audit_repo=_audit_repo,
        jurisdiction_repo=j_repo,
    )
    return svc, _audit_repo, _jurisdiction


# ===========================================================================
# --- Happy path ---
# ===========================================================================


def test_happy_path_short_answer_yes_with_citations() -> None:
    """AnswerQuery produces short_answer in {yes,no,conditional} with
    len(citations)>0 and a populated audit_record_id.
    """
    source_url = "https://denvergov.org/recycling"
    citation = _make_citation(source_url)
    verdict = Accepted()
    llm = _FakeLLM(_make_evaluated_answer(verdict, (citation,)))

    # Build Denver with a GENERATED id (not the 0001 sentinel).
    denver = _make_denver_jurisdiction()
    jid = denver.id
    mat = _make_material("cardboard")
    src_id = SourceId(uuid.uuid4())
    rule_repo = MemRuleRepo()
    source_repo = MemSourceRepo()
    src_doc = SourceDocument(
        id=src_id,
        jurisdiction_id=jid,
        url=source_url,
        title="Denver Recycling Guide",
        authority_level=1,
        fetched_at=datetime.now(tz=UTC),
        source_text="Cardboard is accepted curbside.",
        source_text_hash="abc123",
    )
    source_repo.save(src_doc)
    rule = _make_rule(jid, mat.id, src_id)
    rule_repo.save(rule)

    normalizer = _FakeNormalizer(Resolved(material=mat))
    svc, audit_repo, _ = _build_service(
        normalizer=normalizer,
        llm=llm,
        rule_repo=rule_repo,
        source_repo=source_repo,
        jurisdiction=denver,
    )

    answer = svc.execute(
        AnswerQueryCommand(
            query_text="Can I recycle cardboard?",
            location_input="Denver, CO",
        )
    )

    assert answer.short_answer in {"yes", "no", "conditional"}
    assert len(answer.citations) > 0
    assert answer.audit_record_id != ""

    # Exactly one audit row persisted.
    saved_id = AnswerAuditRecordId(uuid.UUID(answer.audit_record_id))
    assert audit_repo.find_by_id(saved_id) is not None


def test_wire_jurisdiction_id_comes_from_repo_not_hardcoded() -> None:
    source_url = "https://denvergov.org/recycling"
    citation = _make_citation(source_url)
    llm = _FakeLLM(_make_evaluated_answer(Accepted(), (citation,)))

    denver = _make_denver_jurisdiction()  # fresh UUID
    jid = denver.id
    mat = _make_material("cardboard")
    src_id = SourceId(uuid.uuid4())
    rule_repo = MemRuleRepo()
    source_repo = MemSourceRepo()
    src_doc = SourceDocument(
        id=src_id,
        jurisdiction_id=jid,
        url=source_url,
        title="Denver Recycling Guide",
        authority_level=1,
        fetched_at=datetime.now(tz=UTC),
        source_text="Cardboard is accepted curbside.",
        source_text_hash="abc123",
    )
    source_repo.save(src_doc)
    rule_repo.save(_make_rule(jid, mat.id, src_id))

    normalizer = _FakeNormalizer(Resolved(material=mat))
    svc, audit_repo, _ = _build_service(
        normalizer=normalizer,
        llm=llm,
        rule_repo=rule_repo,
        source_repo=source_repo,
        jurisdiction=denver,
    )

    answer = svc.execute(
        AnswerQueryCommand(
            query_text="Can I recycle cardboard?",
            location_input="Denver, CO",
        )
    )

    # Wire id must equal the generated UUID, not any hardcoded sentinel.
    assert answer.jurisdiction.id == str(jid.value)
    # The old sentinel 0001 must NOT be present.
    assert answer.jurisdiction.id != "00000000-0000-0000-0000-000000000001"

    # Audit record must carry the same generated id.
    saved = next(iter(audit_repo._store.values()))
    assert saved.jurisdiction_id == jid


def test_ooj_path_unknown_aurora() -> None:
    svc, audit_repo, _ = _build_service(llm=_NeverCalledLLM())

    answer = svc.execute(
        AnswerQueryCommand(
            query_text="Can I recycle glass?",
            location_input="Aurora",
        )
    )

    assert answer.short_answer == "unknown"
    assert answer.confidence == "low"
    assert "Aurora" in answer.recommended_action
    assert answer.citations == []

    # Exactly one audit row.
    assert len(audit_repo._store) == 1
    saved = next(iter(audit_repo._store.values()))
    assert saved.query_location_input == "Aurora"
    assert saved.no_evaluation_reason == NoEvaluationReason.OUT_OF_JURISDICTION


def test_slug_resolved_but_missing_jurisdiction_row_emits_ooj() -> None:
    audit_repo = MemAnswerAuditRecordRepo()
    empty_j_repo = MemJurisdictionRepo()  # Denver slug resolves, no DB row
    retrieval_svc = RetrievalService(
        material_normalizer=_FakeNormalizer(Uncertain()),  # type: ignore[arg-type]
        rule_repo=MemRuleRepo(),
        source_repo=MemSourceRepo(),
        retrieval_llm=_NeverCalledLLM(),  # type: ignore[arg-type]
    )
    svc = AnswerQuery(
        retrieval_service=retrieval_svc,
        audit_repo=audit_repo,
        jurisdiction_repo=empty_j_repo,
    )

    answer = svc.execute(
        AnswerQueryCommand(
            query_text="Can I recycle cardboard?",
            location_input="Denver",
        )
    )

    assert answer.short_answer == "unknown"
    assert answer.refusal_reason == "out_of_jurisdiction"
    assert answer.citations == []
    assert len(audit_repo._store) == 1
    saved = next(iter(audit_repo._store.values()))
    assert saved.no_evaluation_reason == NoEvaluationReason.OUT_OF_JURISDICTION


def test_ambiguous_material_path() -> None:
    cand1 = _make_material("pet-bottle")
    cand2 = _make_material("hdpe-jug")
    normalizer = _FakeNormalizer(Ambiguous(candidates=(cand1, cand2)))

    svc, audit_repo, _ = _build_service(
        normalizer=normalizer,
        llm=_NeverCalledLLM(),
    )

    answer = svc.execute(
        AnswerQueryCommand(
            query_text="Can I recycle this plastic thing?",
            location_input="Denver, CO",
        )
    )

    assert answer.short_answer == "unknown"
    assert answer.citations == []
    assert answer.clarifying_question is not None
    assert len(answer.clarifying_question) > 0

    # One audit row with correct reason.
    assert len(audit_repo._store) == 1
    saved = next(iter(audit_repo._store.values()))
    assert saved.no_evaluation_reason == NoEvaluationReason.CONFLICTED


def test_uncertain_material_path() -> None:
    normalizer = _FakeNormalizer(Uncertain())

    svc, audit_repo, _ = _build_service(
        normalizer=normalizer,
        llm=_NeverCalledLLM(),
    )

    answer = svc.execute(
        AnswerQueryCommand(
            query_text="Can I recycle stuff?",
            location_input="Denver, CO",
        )
    )

    assert answer.short_answer == "unknown"
    assert answer.citations == []
    assert answer.clarifying_question is not None

    # One audit row with correct reason.
    assert len(audit_repo._store) == 1
    saved = next(iter(audit_repo._store.values()))
    assert saved.no_evaluation_reason == NoEvaluationReason.UNCERTAIN_MATERIAL


def test_validator_rejected_path() -> None:
    # Return Accepted verdict but empty citations -- triggers
    # AnswerAuditRecordValidator violation (INV-PROD-001).
    source_url = "https://denvergov.org/recycling"
    llm = _FakeLLM(
        EvaluatedAnswer(
            verdict=Accepted(),
            citations=(),  # empty -- grounding violation
            recommended_action="Place in the blue bin.",
            confidence="high",
            retrieved_source_urls=frozenset(),
        )
    )

    denver = _make_denver_jurisdiction()
    jid = denver.id
    mat = _make_material("cardboard")
    src_id = SourceId(uuid.uuid4())
    rule_repo = MemRuleRepo()
    source_repo = MemSourceRepo()
    src_doc = SourceDocument(
        id=src_id,
        jurisdiction_id=jid,
        url=source_url,
        title="Denver Recycling Guide",
        authority_level=1,
        fetched_at=datetime.now(tz=UTC),
        source_text="Cardboard is accepted curbside.",
        source_text_hash="abc123",
    )
    source_repo.save(src_doc)
    rule_repo.save(_make_rule(jid, mat.id, src_id))
    normalizer = _FakeNormalizer(Resolved(material=mat))

    svc, audit_repo, _ = _build_service(
        normalizer=normalizer,
        llm=llm,
        rule_repo=rule_repo,
        source_repo=source_repo,
        jurisdiction=denver,
    )

    answer = svc.execute(
        AnswerQueryCommand(
            query_text="Can I recycle cardboard?",
            location_input="Denver, CO",
        )
    )

    assert answer.short_answer == "unknown"
    # Exactly one row -- no double-write.
    assert len(audit_repo._store) == 1
    saved = next(iter(audit_repo._store.values()))
    assert saved.no_evaluation_reason == NoEvaluationReason.VALIDATOR_REJECTED


def test_ungrounded_citation_is_refused() -> None:
    """Accepted verdict citing a URL absent from the retrieved source set is
    refused by the GroundingValidator (INV-LLM-002): short_answer='unknown',
    citations=[], persisted reason VALIDATOR_REJECTED. Distinct from
    test_validator_rejected_path: here the citation exists but its URL
    fails the membership check.
    """
    retrieved_url = "https://denvergov.org/recycling"
    unretrieved_url = "https://not-a-retrieved-source.example/made-up"
    # LLM cites a URL the retrieval set does not contain.
    llm = _FakeLLM(
        _make_evaluated_answer(Accepted(), (_make_citation(unretrieved_url),))
    )

    denver = _make_denver_jurisdiction()
    jid = denver.id
    mat = _make_material("cardboard")
    src_id = SourceId(uuid.uuid4())
    rule_repo = MemRuleRepo()
    source_repo = MemSourceRepo()
    src_doc = SourceDocument(
        id=src_id,
        jurisdiction_id=jid,
        url=retrieved_url,  # the only retrieved source URL
        title="Denver Recycling Guide",
        authority_level=1,
        fetched_at=datetime.now(tz=UTC),
        source_text="Cardboard is accepted curbside.",
        source_text_hash="abc123",
    )
    source_repo.save(src_doc)
    rule_repo.save(_make_rule(jid, mat.id, src_id))
    normalizer = _FakeNormalizer(Resolved(material=mat))

    svc, audit_repo, _ = _build_service(
        normalizer=normalizer,
        llm=llm,
        rule_repo=rule_repo,
        source_repo=source_repo,
        jurisdiction=denver,
    )

    answer = svc.execute(
        AnswerQueryCommand(
            query_text="Can I recycle cardboard?",
            location_input="Denver, CO",
        )
    )

    assert answer.short_answer == "unknown"
    assert answer.citations == []
    assert len(audit_repo._store) == 1
    saved = next(iter(audit_repo._store.values()))
    assert saved.no_evaluation_reason == NoEvaluationReason.VALIDATOR_REJECTED


def test_not_covered_with_citations_is_refused() -> None:
    """A NotCovered verdict carrying citations is refused -- citations on an
    "I can't verify this" answer would lend it false authority. The pipeline
    returns short_answer='unknown', citations=[], VALIDATOR_REJECTED.
    """
    source_url = "https://denvergov.org/recycling"
    llm = _FakeLLM(
        EvaluatedAnswer(
            verdict=NotCovered(),
            citations=(_make_citation(source_url),),
            recommended_action="No matching rule found.",
            confidence="low",
            retrieved_source_urls=frozenset(),
        )
    )

    denver = _make_denver_jurisdiction()
    jid = denver.id
    mat = _make_material("cardboard")
    src_id = SourceId(uuid.uuid4())
    rule_repo = MemRuleRepo()
    source_repo = MemSourceRepo()
    src_doc = SourceDocument(
        id=src_id,
        jurisdiction_id=jid,
        url=source_url,
        title="Denver Recycling Guide",
        authority_level=1,
        fetched_at=datetime.now(tz=UTC),
        source_text="Cardboard is accepted curbside.",
        source_text_hash="abc123",
    )
    source_repo.save(src_doc)
    rule_repo.save(_make_rule(jid, mat.id, src_id))
    normalizer = _FakeNormalizer(Resolved(material=mat))

    svc, audit_repo, _ = _build_service(
        normalizer=normalizer,
        llm=llm,
        rule_repo=rule_repo,
        source_repo=source_repo,
        jurisdiction=denver,
    )

    answer = svc.execute(
        AnswerQueryCommand(
            query_text="Can I recycle cardboard?",
            location_input="Denver, CO",
        )
    )

    assert answer.short_answer == "unknown"
    assert answer.citations == []
    assert len(audit_repo._store) == 1
    saved = next(iter(audit_repo._store.values()))
    assert saved.no_evaluation_reason == NoEvaluationReason.VALIDATOR_REJECTED


# ===========================================================================
# --- _make_record audit provenance ---
# ===========================================================================


def _make_record_args(
    outcome: EvaluatedAnswer,
) -> tuple[AnswerAuditRecordId, AnswerQueryCommand, EvaluatedAnswer]:
    return (
        AnswerAuditRecordId(uuid.uuid4()),
        AnswerQueryCommand(
            query_text="Can I recycle cardboard?",
            location_input="Denver, CO",
        ),
        outcome,
    )


def test_make_record_grades_citations_against_threaded_set() -> None:
    outcome = EvaluatedAnswer(
        verdict=Accepted(),
        citations=(_make_citation("https://denver.gov/recycling"),),
        recommended_action="Place in the blue bin.",
        confidence="high",
        retrieved_source_urls=frozenset(),  # genuine set omits the cited URL
    )
    record_id, command, outcome = _make_record_args(outcome)
    with pytest.raises(AnswerAuditRecordValidationError):
        _make_record(
            record_id,
            command,
            outcome,
            latency_ms=10,
            created_at=datetime.now(tz=UTC),
            jurisdiction=_make_denver_jurisdiction(),
        )


def test_make_record_persists_genuine_retrieved_set() -> None:
    cited = "https://denver.gov/recycling"
    uncited = "https://denver.gov/guidelines"
    outcome = EvaluatedAnswer(
        verdict=Accepted(),
        citations=(_make_citation(cited),),
        recommended_action="Place in the blue bin.",
        confidence="high",
        retrieved_source_urls=frozenset({cited, uncited}),
    )
    record_id, command, outcome = _make_record_args(outcome)
    record = _make_record(
        record_id,
        command,
        outcome,
        latency_ms=10,
        created_at=datetime.now(tz=UTC),
        jurisdiction=_make_denver_jurisdiction(),
    )
    assert record.retrieved_source_urls == frozenset({cited, uncited})


def test_make_record_no_evaluation_has_empty_retrieved_set() -> None:
    record = _make_record(
        AnswerAuditRecordId(uuid.uuid4()),
        AnswerQueryCommand(
            query_text="Can I recycle cardboard?",
            location_input="Denver, CO",
        ),
        NoEvaluation(
            reason=NoEvaluationReason.NO_EVIDENCE,
            recommended_action="No rule found.",
        ),
        latency_ms=10,
        created_at=datetime.now(tz=UTC),
        jurisdiction=_make_denver_jurisdiction(),
    )
    assert record.retrieved_source_urls == frozenset()
    assert record.no_evaluation_reason == NoEvaluationReason.NO_EVIDENCE


# ===========================================================================
# --- repo.save raises ---
# ===========================================================================


@final
class _BrokenAuditRepo:
    """Raises on save() to simulate an integrity failure."""

    def next_identity(self) -> AnswerAuditRecordId:
        return AnswerAuditRecordId(uuid.uuid4())

    def save(self, record: object) -> None:
        raise RuntimeError("DB write failed")

    def find_by_id(self, record_id: AnswerAuditRecordId) -> None:
        return None


def test_save_raises_propagates() -> None:
    """If repo.save raises, the exception propagates -- no swallowing."""
    source_url = "https://denvergov.org/recycling"
    citation = _make_citation(source_url)
    llm = _FakeLLM(_make_evaluated_answer(Accepted(), (citation,)))

    denver = _make_denver_jurisdiction()
    jid = denver.id
    mat = _make_material("cardboard")
    src_id = SourceId(uuid.uuid4())
    rule_repo = MemRuleRepo()
    source_repo = MemSourceRepo()
    src_doc = SourceDocument(
        id=src_id,
        jurisdiction_id=jid,
        url=source_url,
        title="Denver Recycling Guide",
        authority_level=1,
        fetched_at=datetime.now(tz=UTC),
        source_text="Cardboard is accepted curbside.",
        source_text_hash="abc123",
    )
    source_repo.save(src_doc)
    rule_repo.save(_make_rule(jid, mat.id, src_id))
    normalizer = _FakeNormalizer(Resolved(material=mat))

    j_repo = MemJurisdictionRepo()
    j_repo.save(denver)
    retrieval_svc = RetrievalService(
        material_normalizer=normalizer,  # type: ignore[arg-type]
        rule_repo=rule_repo,
        source_repo=source_repo,
        retrieval_llm=llm,  # type: ignore[arg-type]
    )
    broken_repo = _BrokenAuditRepo()
    svc = AnswerQuery(
        retrieval_service=retrieval_svc,
        audit_repo=broken_repo,  # type: ignore[arg-type]
        jurisdiction_repo=j_repo,
    )

    with pytest.raises(RuntimeError, match="DB write failed"):
        svc.execute(
            AnswerQueryCommand(
                query_text="Can I recycle cardboard?",
                location_input="Denver, CO",
            )
        )


def test_llm_rejected_path() -> None:
    """RetrievalLLM returns NoEvaluation(LLM_REJECTED) ->
    short_answer='unknown', audit row with LLM_REJECTED.
    Cite INV-PROD-004.
    """
    llm = _FakeLLM(
        NoEvaluation(
            reason=NoEvaluationReason.LLM_REJECTED,
            recommended_action="Service temporarily unavailable.",
        )
    )

    denver = _make_denver_jurisdiction()
    jid = denver.id
    mat = _make_material("cardboard")
    src_id = SourceId(uuid.uuid4())
    rule_repo = MemRuleRepo()
    source_repo = MemSourceRepo()
    src_doc = SourceDocument(
        id=src_id,
        jurisdiction_id=jid,
        url="https://denvergov.org/recycling",
        title="Denver Recycling Guide",
        authority_level=1,
        fetched_at=datetime.now(tz=UTC),
        source_text="Cardboard is accepted curbside.",
        source_text_hash="abc123",
    )
    source_repo.save(src_doc)
    rule_repo.save(_make_rule(jid, mat.id, src_id))
    normalizer = _FakeNormalizer(Resolved(material=mat))

    svc, audit_repo, _ = _build_service(
        normalizer=normalizer,
        llm=llm,
        rule_repo=rule_repo,
        source_repo=source_repo,
        jurisdiction=denver,
    )

    answer = svc.execute(
        AnswerQueryCommand(
            query_text="Can I recycle cardboard?",
            location_input="Denver, CO",
        )
    )

    assert answer.short_answer == "unknown"
    assert len(audit_repo._store) == 1
    saved = next(iter(audit_repo._store.values()))
    assert saved.no_evaluation_reason == NoEvaluationReason.LLM_REJECTED


def test_item_verdict_sum_completeness_exhaustiveness() -> None:
    """Every variant in ItemVerdict is covered by domain_to_wire mapper.

    Uses typing.get_args on the ItemVerdict union to enumerate variants.
    Introducing a new variant without updating the mapper fails this test.
    """
    # ItemVerdict = Accepted | Refused | NotCovered | Conflicted
    variants = get_args(ItemVerdict)
    assert len(variants) > 0, "ItemVerdict has no variants -- type alias broken"

    for variant_type in variants:
        # Construct a minimal instance of each variant.
        instance = variant_type()
        result = verdict_to_short_answer(instance)
        assert result in {"yes", "no", "conditional", "unknown"}, (
            f"verdict_to_short_answer({variant_type.__name__}) returned "
            f"unexpected value {result!r}"
        )


def test_conflicted_maps_to_conflict_unresolved_refusal() -> None:
    """Conflicted -> short_answer='unknown',
    refusal_reason='conflict_unresolved' (answer.md Verdict mapping).

    Distinct from NotCovered's 'no_evidence': a source conflict is not
    an absence of evidence.
    """
    answer = _make_evaluated_answer(Conflicted(), ())
    result = evaluated_answer_to_wire(
        answer,
        audit_record_id=uuid.uuid4(),
        jurisdiction_id=_make_jurisdiction_id(),
        jurisdiction_name="Denver",
    )

    assert result.short_answer == "unknown"
    assert result.refusal_reason == "conflict_unresolved"
    assert result.citations == []


def test_conflicted_with_citations_surfaces_them_on_unknown() -> None:
    citation = _make_citation("https://denver.gov/recycling")
    answer = _make_evaluated_answer(Conflicted(), (citation,))
    result = evaluated_answer_to_wire(
        answer,
        audit_record_id=uuid.uuid4(),
        jurisdiction_id=_make_jurisdiction_id(),
        jurisdiction_name="Denver",
    )

    assert result.short_answer == "unknown"
    assert result.refusal_reason == "conflict_unresolved"
    assert len(result.citations) == 1
    assert result.citations[0].url == "https://denver.gov/recycling"


def test_get_jurisdiction_page_excludes_superseded_rules() -> None:
    """A superseded Rule (superseded_by IS NOT NULL) does not appear in
    the jurisdiction page output (INV-AUTH-002).
    """
    jid = _make_jurisdiction_id()
    mat = _make_material("cardboard")
    src_id = SourceId(uuid.uuid4())

    # Build active rule and a superseded rule.
    active_rule = _make_rule(jid, mat.id, src_id)
    superseded_rule = Rule(
        id=RuleId(uuid.uuid4()),
        jurisdiction_id=jid,
        material_id=mat.id,
        disposition=Disposition.LANDFILL,
        accepted_status=AcceptedStatus.REJECTED,
        source_document_id=src_id,
        source_quote="Old rule: cardboard goes to landfill.",
        superseded_by=active_rule.id,  # marks it superseded
    )

    rule_repo = MemRuleRepo()
    rule_repo.save(active_rule)
    rule_repo.save(superseded_rule)

    source_repo = MemSourceRepo()
    src_doc = SourceDocument(
        id=src_id,
        jurisdiction_id=jid,
        url="https://denvergov.org/recycling",
        title="Denver Recycling Guide",
        authority_level=1,
        fetched_at=datetime.now(tz=UTC),
        source_text="Cardboard is accepted curbside.",
        source_text_hash="abc123",
    )
    source_repo.save(src_doc)

    jurisdiction = Jurisdiction(
        id=jid,
        name="Denver",
        slug="denver-co-us",
        type=JurisdictionType.CITY,
        country="US",
        supported_status=SupportedStatus.SUPPORTED,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    jurisdiction_repo = MemJurisdictionRepo()
    jurisdiction_repo.save(jurisdiction)

    material_repo = MemMaterialRepo()
    material_repo.save(mat)

    use_case = GetJurisdictionPage(
        jurisdiction_repo=jurisdiction_repo,
        material_repo=material_repo,
        rule_repo=rule_repo,
        source_repo=source_repo,
    )

    page = use_case.execute("denver-co-us")
    assert page is not None

    # Only the active rule's disposition should appear -- rejected
    # (superseded) disposition must not be in the materials list.
    dispositions_in_page = [m.accepted_status for m in page.materials]
    # The active rule has AcceptedStatus.ACCEPTED -> accepted_status='accepted'
    # The superseded rule has AcceptedStatus.REJECTED -- must not appear.
    assert all(d != "rejected" for d in dispositions_in_page), (
        "Superseded rule disposition appeared in jurisdiction page "
        "(INV-AUTH-002 violation)"
    )


def test_construction_time_fallback_wire_matches_persisted_record() -> None:
    """When the AnswerAuditRecordValidator fires at construction time
    (construction-time last-line defense), the wire response must match
    the persisted fallback record -- both must be VALIDATOR_REJECTED, not
    the original EvaluatedAnswer that failed validation.

    outcome is rebound to the fallback before
    _to_wire() is called (INV-PROD-001).
    """
    # Inject a fake RetrievalService that returns an EvaluatedAnswer
    # with Accepted verdict but no citations -- this bypasses the
    # GroundingValidator (which lives inside RetrievalService) and directly
    # hits the construction-time AnswerAuditRecordValidator.
    fake_svc = _FakeRetrievalService(
        answer_result=EvaluatedAnswer(
            verdict=Accepted(),
            citations=(),  # no citations -- construction-time validator fires
            recommended_action="Place in the blue bin.",
            confidence="high",
            retrieved_source_urls=frozenset(),
        )
    )
    audit_repo = MemAnswerAuditRecordRepo()
    denver = _make_denver_jurisdiction()
    j_repo = MemJurisdictionRepo()
    j_repo.save(denver)
    svc = AnswerQuery(
        # RetrievalService is @final; subclassing is forbidden;
        # fake substitution test-only.
        retrieval_service=fake_svc,  # type: ignore[arg-type]  # pyright: ignore[reportArgumentType]
        audit_repo=audit_repo,
        jurisdiction_repo=j_repo,
    )

    answer = svc.execute(
        AnswerQueryCommand(
            query_text="Can I recycle cardboard?",
            location_input="Denver, CO",
        )
    )

    # Wire response must reflect the fallback, not the original EvaluatedAnswer.
    assert answer.short_answer == "unknown"
    assert answer.refusal_reason == "no_evidence"

    # The persisted record must also reflect VALIDATOR_REJECTED.
    assert len(audit_repo._store) == 1
    saved = next(iter(audit_repo._store.values()))
    assert saved.no_evaluation_reason == NoEvaluationReason.VALIDATOR_REJECTED


def test_no_evidence_mapper_produces_unknown_with_no_evidence_refusal() -> None:
    """NoEvaluation(reason=NO_EVIDENCE) maps to short_answer='unknown' and
    refusal_reason='no_evidence' via no_evaluation_to_wire.
    """
    outcome = NoEvaluation(
        reason=NoEvaluationReason.NO_EVIDENCE,
        recommended_action=(
            "No recycling rule found for this material in the queried "
            "jurisdiction."
        ),
        clarifying_question=None,
    )
    jid = JurisdictionId(uuid.uuid4())
    result = no_evaluation_to_wire(
        outcome,
        audit_record_id=uuid.uuid4(),
        location_input="Denver, CO",
        jurisdiction_id=jid,
        jurisdiction_name="Denver",
    )

    assert result.short_answer == "unknown"
    assert result.refusal_reason == "no_evidence"
    assert result.clarifying_question is None
    assert result.citations == []


def test_jurisdiction_name_from_repo_not_hardcoded() -> None:
    """The wire jurisdiction.name must come from the Jurisdiction entity
    fetched from the repo, not from a hardcoded literal.

    The repo is seeded with "City and County of Denver" which must reach
    the wire response unchanged.
    """
    source_url = "https://denvergov.org/recycling"
    citation = _make_citation(source_url)
    verdict = Accepted()
    llm = _FakeLLM(_make_evaluated_answer(verdict, (citation,)))

    denver = _make_denver_jurisdiction()
    jid = denver.id
    mat = _make_material("cardboard")
    src_id = SourceId(uuid.uuid4())
    rule_repo = MemRuleRepo()
    source_repo = MemSourceRepo()
    src_doc = SourceDocument(
        id=src_id,
        jurisdiction_id=jid,
        url=source_url,
        title="Denver Recycling Guide",
        authority_level=1,
        fetched_at=datetime.now(tz=UTC),
        source_text="Cardboard is accepted curbside.",
        source_text_hash="abc123",
    )
    source_repo.save(src_doc)
    rule_repo.save(_make_rule(jid, mat.id, src_id))

    normalizer = _FakeNormalizer(Resolved(material=mat))
    svc, _, _ = _build_service(
        normalizer=normalizer,
        llm=llm,
        rule_repo=rule_repo,
        source_repo=source_repo,
        jurisdiction=denver,
    )

    answer = svc.execute(
        AnswerQueryCommand(
            query_text="Can I recycle cardboard?",
            location_input="Denver, CO",
        )
    )

    # The canonical name must be "City and County of Denver" -- sourced from
    # the Jurisdiction entity in the repo, not any hardcoded string.
    assert answer.jurisdiction.name == "City and County of Denver"
    assert answer.jurisdiction.id is not None
