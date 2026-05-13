"""Tests for ItemVerdict variants -- in particular tuple-coercion of
mutable inputs on frozen Value Objects."""

from src.domain.retrieval.item_verdict import Accepted


class TestAcceptedCoercesConditions:
    """Accepted.conditions is declared `tuple[str, ...]`; lists passed at
    construction must be coerced to tuple so the frozen Value's
    immutability guarantee holds at runtime."""

    def test_list_conditions_stored_as_tuple(self) -> None:
        a = Accepted(conditions=["empty", "rinse"])  # pyright: ignore[reportArgumentType]
        assert isinstance(a.conditions, tuple)
        assert a.conditions == ("empty", "rinse")

    def test_empty_list_conditions_stored_as_empty_tuple(self) -> None:
        a = Accepted(conditions=[])  # pyright: ignore[reportArgumentType]
        assert isinstance(a.conditions, tuple)
        assert a.conditions == ()

    def test_default_conditions_is_empty_tuple(self) -> None:
        a = Accepted()
        assert isinstance(a.conditions, tuple)
        assert a.conditions == ()
