"""Tests for the NormalizationResult sum type."""

import uuid

import pytest

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


def _make_material(slug: str) -> Material:
    return Material(
        id=MaterialId(uuid.uuid4()),
        canonical_name=slug.replace("-", " ").title(),
        slug=slug,
        category=MaterialCategory.PLASTIC,
    )


class TestResolved:
    def test_holds_material(self) -> None:
        m = _make_material("cardboard")
        assert Resolved(material=m).material is m


class TestAmbiguous:
    def test_holds_candidates(self) -> None:
        c1 = _make_material("pet")
        c2 = _make_material("hdpe")
        assert Ambiguous(candidates=(c1, c2)).candidates == (c1, c2)

    def test_rejects_single_candidate(self) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            _ = Ambiguous(candidates=(_make_material("only"),))

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
        r: NormalizationResult = Resolved(material=_make_material("paper"))
        assert isinstance(r, Resolved)

    def test_ambiguous_is_a_normalization_result(self) -> None:
        a: NormalizationResult = Ambiguous(
            candidates=(_make_material("a"), _make_material("b"))
        )
        assert isinstance(a, Ambiguous)

    def test_uncertain_is_a_normalization_result(self) -> None:
        u: NormalizationResult = Uncertain()
        assert isinstance(u, Uncertain)
