"""Tests for the Query value's constructor guards (INV-LLM-004)."""

import pytest

from src.domain.retrieval.query import QUERY_MAX_LENGTH, Query


class TestQueryLengthGuard:
    def test_text_at_max_length_is_accepted(self) -> None:
        query = Query(text="a" * QUERY_MAX_LENGTH, location_input="Denver")
        assert len(query.text) == QUERY_MAX_LENGTH

    def test_text_over_max_length_raises(self) -> None:
        too_long = "a" * (QUERY_MAX_LENGTH + 1)
        with pytest.raises(ValueError, match="INV-LLM-004"):
            _ = Query(text=too_long, location_input="Denver")


class TestQueryBlankGuard:
    def test_empty_text_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be blank"):
            _ = Query(text="", location_input="Denver")

    def test_whitespace_only_text_raises(self) -> None:
        with pytest.raises(ValueError, match="must not be blank"):
            _ = Query(text="   ", location_input="Denver")
