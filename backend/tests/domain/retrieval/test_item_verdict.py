"""Tests for ItemVerdict variants -- Accepted.conditions and citations
immutability contracts, Refused/Conflicted.citations guards, and
citations_of() helper."""

from typing import cast

import pytest

from src.domain.retrieval.citation import Citation
from src.domain.retrieval.item_verdict import (
    Accepted,
    Conflicted,
    NotCovered,
    Refused,
    citations_of,
)

_CITE = Citation(title="Denver Recycling", url="https://denvergov.org/r")


class TestAcceptedConditions:
    """Accepted.conditions is declared `tuple[str, ...]`. The frozen
    Value's immutability rests on the declared type; the constructor
    rejects a non-tuple at runtime rather than coercing it, so a
    boundary caller that violates the declared type fails fast."""

    def test_default_conditions_is_empty_tuple(self) -> None:
        a = Accepted()
        assert isinstance(a.conditions, tuple)
        assert a.conditions == ()

    def test_tuple_conditions_stored_as_is(self) -> None:
        a = Accepted(conditions=("empty", "rinse"))
        assert isinstance(a.conditions, tuple)
        assert a.conditions == ("empty", "rinse")

    def test_list_conditions_raises_type_error(self) -> None:
        raw = cast(object, ["empty", "rinse"])
        bad = cast(tuple[str, ...], raw)
        with pytest.raises(TypeError, match="conditions must be a tuple"):
            _ = Accepted(conditions=bad)


class TestCitationsTypeGuards:
    """citations is `tuple[Citation, ...]` on Accepted, Refused, Conflicted.
    Each constructor rejects a non-tuple at runtime rather than coercing,
    so a boundary caller that violates the declared type fails fast."""

    def test_accepted_list_citations_raises_type_error(self) -> None:
        raw = cast(object, [_CITE])
        bad = cast(tuple[Citation, ...], raw)
        with pytest.raises(
            TypeError, match="Accepted.citations must be a tuple"
        ):
            _ = Accepted(citations=bad)

    def test_refused_list_citations_raises_type_error(self) -> None:
        raw = cast(object, [_CITE])
        bad = cast(tuple[Citation, ...], raw)
        with pytest.raises(
            TypeError, match="Refused.citations must be a tuple"
        ):
            _ = Refused(citations=bad)

    def test_conflicted_list_citations_raises_type_error(self) -> None:
        raw = cast(object, [_CITE])
        bad = cast(tuple[Citation, ...], raw)
        with pytest.raises(
            TypeError, match="Conflicted.citations must be a tuple"
        ):
            _ = Conflicted(citations=bad)


class TestCitationsOf:
    """citations_of() returns the verdict's citations tuple, or () for
    NotCovered."""

    def test_accepted_returns_citations(self) -> None:
        v = Accepted(citations=(_CITE,))
        assert citations_of(v) == (_CITE,)

    def test_refused_returns_citations(self) -> None:
        v = Refused(citations=(_CITE,))
        assert citations_of(v) == (_CITE,)

    def test_conflicted_returns_citations(self) -> None:
        v = Conflicted(citations=(_CITE,))
        assert citations_of(v) == (_CITE,)

    def test_not_covered_returns_empty(self) -> None:
        assert citations_of(NotCovered()) == ()
