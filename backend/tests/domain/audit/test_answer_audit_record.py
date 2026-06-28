"""Tests for AnswerAuditRecord aggregate root."""

import uuid
from datetime import UTC, datetime
from typing import cast

import pytest

from src.domain.audit.answer_audit_record import (
    AnswerAuditRecordId,
)
from src.domain.exceptions import AnswerAuditRecordValidationError
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.retrieval.citation import Citation
from src.domain.retrieval.item_verdict import (
    Accepted,
    Conflicted,
    NotCovered,
    Refused,
    citations_of,
)
from tests.utils.builders import make_answer_audit_record, make_citation

_J_ID = JurisdictionId(uuid.uuid4())
_SOURCE_URL = "https://denvergov.org/recycling"
_NOW = datetime.now(tz=UTC)


class TestAnswerAuditRecordConstruction:
    """Valid construction paths."""

    def test_accepted_with_citation_succeeds(self) -> None:
        rec = make_answer_audit_record(
            verdict=Accepted(),
            citations=(make_citation(),),
            retrieved_source_urls=frozenset([_SOURCE_URL]),
            query_text="Can I recycle cardboard?",
        )
        assert rec.query_text == "Can I recycle cardboard?"

    def test_refused_definitive_with_citation_succeeds(self) -> None:
        rec = make_answer_audit_record(
            verdict=Refused(),
            citations=(make_citation(),),
            retrieved_source_urls=frozenset([_SOURCE_URL]),
        )
        assert isinstance(rec.verdict, Refused)

    def test_not_covered_empty_citations_succeeds(self) -> None:
        rec = make_answer_audit_record(
            verdict=NotCovered(),
            citations=(),
            retrieved_source_urls=frozenset(),
        )
        assert citations_of(rec.verdict) == ()

    def test_conflicted_with_citation_succeeds(self) -> None:
        rec = make_answer_audit_record(
            verdict=Conflicted(),
            citations=(make_citation(),),
            retrieved_source_urls=frozenset([_SOURCE_URL]),
        )
        assert isinstance(rec.verdict, Conflicted)


class TestINVPROD001EnforcedAtConstruction:
    """INV-PROD-001: definitive verdicts require non-empty citations."""

    def test_accepted_empty_citations_raises(self) -> None:
        with pytest.raises(AnswerAuditRecordValidationError):
            _ = make_answer_audit_record(
                verdict=Accepted(),
                citations=(),
                retrieved_source_urls=frozenset(),
            )

    def test_refused_empty_citations_raises(self) -> None:
        with pytest.raises(AnswerAuditRecordValidationError):
            _ = make_answer_audit_record(
                verdict=Refused(),
                citations=(),
                retrieved_source_urls=frozenset(),
            )

    def test_conflicted_empty_citations_raises(self) -> None:
        with pytest.raises(AnswerAuditRecordValidationError):
            _ = make_answer_audit_record(
                verdict=Conflicted(),
                citations=(),
                retrieved_source_urls=frozenset(),
            )


class TestINVLLM002EnforcedAtConstruction:
    """INV-LLM-002: citation URLs must be members of retrieved source set."""

    def test_citation_url_not_in_retrieved_set_raises(self) -> None:
        bad_url = "https://hallucinated.example.com/page"
        with pytest.raises(AnswerAuditRecordValidationError):
            _ = make_answer_audit_record(
                verdict=Accepted(),
                citations=(make_citation(url=bad_url),),
                retrieved_source_urls=frozenset([_SOURCE_URL]),
            )

    def test_citation_url_in_retrieved_set_passes(self) -> None:
        rec = make_answer_audit_record(
            verdict=Accepted(),
            citations=(make_citation(url=_SOURCE_URL),),
            retrieved_source_urls=frozenset([_SOURCE_URL]),
        )
        assert len(citations_of(rec.verdict)) == 1


class TestCitationsTypeGuard:
    """Accepted.citations is `tuple[Citation, ...]`. The constructor rejects
    a non-tuple at runtime rather than coercing it, so a boundary caller
    that violates the declared type fails fast (per architecture.md
    § Tuple boundary-guard idiom).
    """

    def test_list_citations_raises_type_error(self) -> None:
        # Launder the intentionally-wrong list through object so the
        # runtime guard is what rejects it -- no suppressed diagnostic.
        # basedpyright requires the object hop for a cast between
        # non-overlapping types.
        raw = cast(object, [make_citation()])
        bad = cast(tuple[Citation, ...], raw)
        with pytest.raises(TypeError, match="citations must be a tuple"):
            _ = Accepted(citations=bad)

    def test_tuple_citations_succeeds(self) -> None:
        rec = make_answer_audit_record(
            verdict=Accepted(),
            citations=(make_citation(),),
            retrieved_source_urls=frozenset([_SOURCE_URL]),
        )
        assert isinstance(citations_of(rec.verdict), tuple)
        assert len(citations_of(rec.verdict)) == 1


class TestAnswerAuditRecordId:
    """AnswerAuditRecordId is a typed Value."""

    def test_same_uuid_equals(self) -> None:
        uid = uuid.uuid4()
        assert AnswerAuditRecordId(uid) == AnswerAuditRecordId(uid)

    def test_different_uuid_not_equal(self) -> None:
        assert AnswerAuditRecordId(uuid.uuid4()) != AnswerAuditRecordId(
            uuid.uuid4()
        )
