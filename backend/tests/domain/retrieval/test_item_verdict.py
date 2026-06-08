"""Tests for ItemVerdict variants -- Accepted.conditions immutability
contract."""

from typing import cast

import pytest

from src.domain.retrieval.item_verdict import Accepted


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
