"""Tests for LocationResolver pure function.

TDD red step: written before implementation exists.
"""

import pytest

from src.domain.retrieval.location_resolver import (
    DENVER_JURISDICTION_ID,
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
    """City-name aliases all return the Denver JurisdictionId."""

    def test_denver_bare(self) -> None:
        assert resolve_location("Denver") == DENVER_JURISDICTION_ID

    def test_denver_co(self) -> None:
        assert resolve_location("Denver, CO") == DENVER_JURISDICTION_ID

    def test_denver_colorado(self) -> None:
        assert resolve_location("Denver, Colorado") == DENVER_JURISDICTION_ID

    def test_city_and_county(self) -> None:
        assert (
            resolve_location("City and County of Denver")
            == DENVER_JURISDICTION_ID
        )

    def test_case_insensitive(self) -> None:
        assert resolve_location("denver") == DENVER_JURISDICTION_ID
        assert resolve_location("DENVER") == DENVER_JURISDICTION_ID
        assert resolve_location("denver, co") == DENVER_JURISDICTION_ID

    def test_leading_trailing_whitespace_trimmed(self) -> None:
        assert resolve_location("  Denver  ") == DENVER_JURISDICTION_ID


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
        assert resolve_location(zip_code) == DENVER_JURISDICTION_ID

    def test_zip_case_insensitive_does_not_matter_digits(self) -> None:
        # ZIPs are digits; whitespace-trim still applies
        assert resolve_location("  80201  ") == DENVER_JURISDICTION_ID
