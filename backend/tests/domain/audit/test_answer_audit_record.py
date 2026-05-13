"""Tests for AnswerAuditRecord aggregate root.

TDD red step: written before implementation exists.
"""

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.audit.answer_audit_record import (
    AnswerAuditRecord,
    AnswerAuditRecordId,
)
from src.domain.exceptions import AnswerAuditRecordValidationError
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.retrieval.citation import Citation
from src.domain.retrieval.item_verdict import (
    Accepted,
    Conflicted,
    ItemVerdict,
    NotCovered,
    Refused,
)

_J_ID = JurisdictionId(uuid.uuid4())
_SOURCE_URL = "https://denvergov.org/recycling"
_NOW = datetime.now(tz=UTC)


def _make_citation(url: str = _SOURCE_URL) -> Citation:
    return Citation(title="Denver Recycling", url=url)


def _make_record(
    verdict: ItemVerdict,
    citations: list[Citation],
    retrieved_source_urls: frozenset[str],
    *,
    rec_id: AnswerAuditRecordId | None = None,
) -> AnswerAuditRecord:
    return AnswerAuditRecord(
        id=rec_id or AnswerAuditRecordId(uuid.uuid4()),
        query_text="Can I recycle cardboard?",
        query_location_input="Denver",
        jurisdiction_id=_J_ID,
        verdict=verdict,
        citations=citations,
        retrieved_source_urls=retrieved_source_urls,
        recommended_action="Yes, recycle it curbside.",
        prompt_version="ask_compose_v1",
        model_id="claude-sonnet-4-6",
        latency_ms=1200,
        created_at=_NOW,
    )


class TestAnswerAuditRecordConstruction:
    """Valid construction paths."""

    def test_accepted_with_citation_succeeds(self) -> None:
        rec = _make_record(
            Accepted(conditions=[]),
            [_make_citation()],
            frozenset([_SOURCE_URL]),
        )
        assert rec.query_text == "Can I recycle cardboard?"

    def test_refused_definitive_with_citation_succeeds(self) -> None:
        rec = _make_record(
            Refused(),
            [_make_citation()],
            frozenset([_SOURCE_URL]),
        )
        assert isinstance(rec.verdict, Refused)

    def test_not_covered_empty_citations_succeeds(self) -> None:
        rec = _make_record(
            NotCovered(),
            [],
            frozenset(),
        )
        assert rec.citations == []

    def test_conflicted_with_citation_succeeds(self) -> None:
        rec = _make_record(
            Conflicted(),
            [_make_citation()],
            frozenset([_SOURCE_URL]),
        )
        assert isinstance(rec.verdict, Conflicted)


class TestINVPROD001EnforcedAtConstruction:
    """INV-PROD-001: definitive verdicts require non-empty citations."""

    def test_accepted_empty_citations_raises(self) -> None:
        with pytest.raises(AnswerAuditRecordValidationError):
            _ = _make_record(Accepted(conditions=[]), [], frozenset())

    def test_refused_empty_citations_raises(self) -> None:
        with pytest.raises(AnswerAuditRecordValidationError):
            _ = _make_record(Refused(), [], frozenset())

    def test_conflicted_empty_citations_raises(self) -> None:
        with pytest.raises(AnswerAuditRecordValidationError):
            _ = _make_record(Conflicted(), [], frozenset())


class TestINVLLM002EnforcedAtConstruction:
    """INV-LLM-002: citation URLs must be members of retrieved source set."""

    def test_citation_url_not_in_retrieved_set_raises(self) -> None:
        bad_url = "https://hallucinated.example.com/page"
        with pytest.raises(AnswerAuditRecordValidationError):
            _ = _make_record(
                Accepted(conditions=[]),
                [_make_citation(url=bad_url)],
                frozenset([_SOURCE_URL]),  # does not contain bad_url
            )

    def test_citation_url_in_retrieved_set_passes(self) -> None:
        rec = _make_record(
            Accepted(conditions=[]),
            [_make_citation(url=_SOURCE_URL)],
            frozenset([_SOURCE_URL]),
        )
        assert len(rec.citations) == 1


class TestAnswerAuditRecordId:
    """AnswerAuditRecordId is a typed Value."""

    def test_same_uuid_equals(self) -> None:
        uid = uuid.uuid4()
        assert AnswerAuditRecordId(uid) == AnswerAuditRecordId(uid)

    def test_different_uuid_not_equal(self) -> None:
        assert AnswerAuditRecordId(uuid.uuid4()) != AnswerAuditRecordId(
            uuid.uuid4()
        )
