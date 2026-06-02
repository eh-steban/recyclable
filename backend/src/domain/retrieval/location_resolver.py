#: Canonical slug for Denver; matches the seed row's slug column.
DENVER_SLUG: str = "denver-co-us"

# ---------------------------------------------------------------------------
# City-name aliases (spec § Location resolver)
# ---------------------------------------------------------------------------

_CITY_NAME_ALIASES: frozenset[str] = frozenset(
    {
        "denver",
        "denver, co",
        "denver, colorado",
        "city and county of denver",
    }
)

# ---------------------------------------------------------------------------
# Denver ZIP set verbatim from spec § Location resolver
# Source: https://en.wikipedia.org/wiki/Denver
# ---------------------------------------------------------------------------


def _zip_range(start: int, end: int) -> frozenset[str]:
    return frozenset(str(z) for z in range(start, end + 1))


_DENVER_ZIPS: frozenset[str] = (
    frozenset({"80012", "80014", "80022", "80033", "80123"})
    | _zip_range(80201, 80212)
    | _zip_range(80214, 80239)
    | frozenset({"80241"})
    | _zip_range(80243, 80244)
    | _zip_range(80246, 80252)
    | _zip_range(80256, 80257)
    | _zip_range(80259, 80261)
    | _zip_range(80263, 80266)
    | frozenset({"80271"})
    | _zip_range(80273, 80274)
    | _zip_range(80279, 80281)
    | _zip_range(80290, 80291)
    | _zip_range(80293, 80295)
    | frozenset({"80299"})
)


def resolve_location(location_input: str) -> str | None:
    """Resolve a user-supplied location string to a canonical jurisdiction slug.

    Case-insensitive, whitespace-trimmed match against the Denver alias
    set. Returns None for anything not in the set.

    Args:
        location_input: raw location text from the user (city name or ZIP).

    Returns:
        DENVER_SLUG on a hit (city-name alias or Denver ZIP); None on a
        miss. The caller looks up the real Jurisdiction via JurisdictionRepo
        using the returned slug.
    """
    normalised = location_input.strip().lower()
    if not normalised:
        return None
    if normalised in _CITY_NAME_ALIASES:
        return DENVER_SLUG
    if normalised in _DENVER_ZIPS:
        return DENVER_SLUG
    return None
