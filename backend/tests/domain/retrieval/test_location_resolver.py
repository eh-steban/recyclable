"""Tests for resolve_location -- returns the canonical slug on a hit."""

import pytest

from src.domain.retrieval.location_resolver import (
    DENVER_SLUG,
    resolve_location,
)


class TestLocationResolverNonDenver:
    """Locations that must return None -- not in the Denver alias set."""

    def test_aurora_returns_none(self) -> None:
        assert resolve_location("Aurora") is None

    def test_boulder_returns_none(self) -> None:
        assert resolve_location("Boulder") is None

    def test_denver_tx_returns_none(self) -> None:
        assert resolve_location("Denver, TX") is None

    def test_empty_string_returns_none(self) -> None:
        assert resolve_location("") is None

    def test_zip_outside_set_returns_none(self) -> None:
        assert resolve_location("80000") is None

    def test_unrelated_city_returns_none(self) -> None:
        assert resolve_location("New York") is None


class TestLocationResolverCityNames:
    """City-name aliases all return the Denver slug."""

    def test_denver_bare(self) -> None:
        result = resolve_location("Denver")
        assert result == DENVER_SLUG

    def test_denver_co(self) -> None:
        result = resolve_location("Denver, CO")
        assert result == DENVER_SLUG

    def test_denver_colorado(self) -> None:
        result = resolve_location("Denver, Colorado")
        assert result == DENVER_SLUG

    def test_city_and_county(self) -> None:
        result = resolve_location("City and County of Denver")
        assert result == DENVER_SLUG

    def test_case_insensitive(self) -> None:
        for alias in ("denver", "DENVER", "denver, co"):
            result = resolve_location(alias)
            assert result == DENVER_SLUG, f"Expected slug hit for {alias!r}"

    def test_leading_trailing_whitespace_trimmed(self) -> None:
        result = resolve_location("  Denver  ")
        assert result == DENVER_SLUG

    def test_hit_returns_slug_string(self) -> None:
        """A city-name hit returns the DENVER_SLUG string constant."""
        assert resolve_location("Denver") == DENVER_SLUG


class TestLocationResolverZipCodes:
    """Spot-checks from the Wikipedia Denver ZIP set."""

    @pytest.mark.parametrize(
        "zip_code",
        [
            "80201",
            "80202",
            "80203",
            "80210",
            "80212",
            "80214",
            "80220",
            "80230",
            "80239",
            "80241",
            "80243",
            "80246",
            "80249",
            "80250",
            "80251",
            "80252",
            "80256",
            "80257",
            "80259",
            "80260",
            "80261",
            "80263",
            "80265",
            "80266",
            "80271",
            "80273",
            "80274",
            "80279",
            "80280",
            "80281",
            "80290",
            "80291",
            "80293",
            "80294",
            "80295",
            "80299",
            # Edge entries from ranges listed in the spec
            "80012",
            "80014",
            "80022",
            "80033",
            "80123",
        ],
    )
    def test_denver_zip_resolves(self, zip_code: str) -> None:
        result = resolve_location(zip_code)
        assert result == DENVER_SLUG, (
            f"Expected Denver slug for ZIP {zip_code!r}"
        )

    def test_zip_whitespace_trimmed(self) -> None:
        result = resolve_location("  80201  ")
        assert result == DENVER_SLUG
