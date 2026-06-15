"""Tests for the NormalizationResult sum type."""

import pytest

from src.domain.knowledge_base.normalization_result import (
    Ambiguous,
    NormalizationResult,
    Resolved,
    Uncertain,
)
from tests.utils.builders import make_material


class TestResolved:
    def test_holds_material(self) -> None:
        m = make_material(slug="cardboard")
        assert Resolved(material=m).material is m


class TestAmbiguous:
    def test_holds_candidates(self) -> None:
        c1 = make_material(slug="pet")
        c2 = make_material(slug="hdpe")
        assert Ambiguous(candidates=(c1, c2)).candidates == (c1, c2)

    def test_rejects_single_candidate(self) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            _ = Ambiguous(candidates=(make_material(slug="only"),))

    def test_rejects_empty_candidates(self) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            _ = Ambiguous(candidates=())


class TestUncertain:
    def test_constructs(self) -> None:
        assert isinstance(Uncertain(), Uncertain)

    def test_equality_by_value(self) -> None:
        assert Uncertain() == Uncertain()


class TestNormalizationResultAlias:
    """Each variant is a member of the NormalizationResult sum."""

    def test_resolved_is_a_normalization_result(self) -> None:
        r: NormalizationResult = Resolved(material=make_material(slug="paper"))
        assert isinstance(r, Resolved)

    def test_ambiguous_is_a_normalization_result(self) -> None:
        a: NormalizationResult = Ambiguous(
            candidates=(make_material(slug="a"), make_material(slug="b"))
        )
        assert isinstance(a, Ambiguous)

    def test_uncertain_is_a_normalization_result(self) -> None:
        u: NormalizationResult = Uncertain()
        assert isinstance(u, Uncertain)
