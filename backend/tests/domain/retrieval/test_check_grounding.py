"""Unit tests for the shared check_grounding predicate.

Pins INV-PROD-001 (definitive verdict requires a citation; a non-definitive
NotCovered must carry none) and INV-LLM-002 (every citation URL is in the
retrieved source set).
"""

from src.domain.retrieval.check_grounding import check_grounding
from src.domain.retrieval.citation import Citation
from src.domain.retrieval.item_verdict import Accepted, NotCovered

_URL = "https://denvergov.org/recycling"


def _cite(url: str) -> Citation:
    return Citation(title="Denver Recycling", url=url)


def test_definitive_with_retrieved_citation_is_grounded() -> None:
    assert check_grounding(Accepted(), [_cite(_URL)], frozenset({_URL})) is True


def test_definitive_without_citations_is_ungrounded() -> None:
    assert check_grounding(Accepted(), [], frozenset({_URL})) is False


def test_definitive_with_unretrieved_url_is_ungrounded() -> None:
    cite = _cite("https://not-a-retrieved-source.example/x")
    assert check_grounding(Accepted(), [cite], frozenset({_URL})) is False


def test_not_covered_without_citations_is_grounded() -> None:
    assert check_grounding(NotCovered(), [], frozenset({_URL})) is True


def test_not_covered_with_citations_is_ungrounded() -> None:
    """NotCovered claims no evidence, so any citation is a grounding leak.

    A citation on an "I can't verify this" answer lends it false authority;
    the predicate must reject it regardless of URL membership.
    """
    assert (
        check_grounding(NotCovered(), [_cite(_URL)], frozenset({_URL})) is False
    )
