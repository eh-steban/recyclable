"""Contract tests for the shared domain builders.

Pins the two guarantees every builder makes: a bare call yields an
invariant-valid object, and the grounded Values (EvaluatedAnswer,
AnswerAuditRecord) default to a citation set that satisfies INV-LLM-002.
A future edit that weakens a default fails here instead of silently
shipping invalid fixtures to every test that relies on the builders.
"""

from src.domain.knowledge_base.jurisdiction import Jurisdiction
from src.domain.knowledge_base.material import Material
from src.domain.knowledge_base.rule import Rule
from src.domain.knowledge_base.source import SourceDocument
from src.domain.retrieval.evaluated_answer import EvaluatedAnswer
from src.domain.retrieval.item_verdict import Accepted
from tests.utils.builders import (
    make_answer_audit_record,
    make_citation,
    make_evaluated_answer,
    make_jurisdiction,
    make_material,
    make_rule,
    make_source_document,
)


def test_knowledge_base_builders_are_valid_by_default() -> None:
    """Bare calls construct without tripping any __post_init__ invariant."""
    assert isinstance(make_jurisdiction(), Jurisdiction)
    assert isinstance(make_material(), Material)
    assert isinstance(make_rule(), Rule)
    assert isinstance(make_source_document(), SourceDocument)
    assert make_citation().url


def test_make_rule_threads_a_shared_jurisdiction_id() -> None:
    jurisdiction = make_jurisdiction()
    rule = make_rule(jurisdiction_id=jurisdiction.id)
    assert rule.jurisdiction_id == jurisdiction.id


def test_make_evaluated_answer_is_grounded_by_default() -> None:
    """Default answer is an Accepted verdict whose citations are all in the
    retrieved set (INV-PROD-001, INV-LLM-002)."""
    answer = make_evaluated_answer()
    assert isinstance(answer, EvaluatedAnswer)
    assert isinstance(answer.verdict, Accepted)
    assert answer.citations
    assert {c.url for c in answer.citations} <= answer.retrieved_source_urls


def test_make_answer_audit_record_is_grounded_by_default() -> None:
    record = make_answer_audit_record()
    assert isinstance(record.verdict, Accepted)
    assert {c.url for c in record.citations} <= record.retrieved_source_urls
