"""LocationResolver -- pure function over a literal Denver alias set.

Spec § Location resolver: case-insensitive, whitespace-trimmed match.
Anything not in the set returns None, which the application service maps
to NoEvaluation(reason=OutOfJurisdiction).

The alias set is the Denver city-name aliases plus the Denver ZIP set
sourced from Wikipedia's Denver article
(https://en.wikipedia.org/wiki/Denver), verbatim per spec:

    80012, 80014, 80022, 80033, 80123,
    80201-80212, 80214-80239,
    80241, 80243-80244, 80246-80252, 80256-80257,
    80259-80261, 80263-80266,
    80271, 80273-80274, 80279-80281,
    80290-80291, 80293-80295, 80299

The DENVER_JURISDICTION_ID is the seeded Denver row's UUID. At MVP this
is a hard-coded sentinel; Phase 4 will wire the actual Postgres UUID via
the boot configuration.
"""

import uuid

from src.domain.knowledge_base.jurisdiction import JurisdictionId

# ---------------------------------------------------------------------------
# Sentinel Denver JurisdictionId
# The seeded Denver jurisdiction UUID. Must match the seed data.
# ---------------------------------------------------------------------------

#: Sentinel UUID used for Denver in the literal alias lookup.
#: Replaced by the real Postgres row UUID when Phase 4 infra lands.
DENVER_JURISDICTION_ID = JurisdictionId(
    uuid.UUID("00000000-0000-0000-0000-000000000001")
)

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


def resolve_location(location_input: str) -> JurisdictionId | None:
    """Resolve a user-supplied location string to a JurisdictionId.

    Case-insensitive, whitespace-trimmed match against the Denver alias
    set. Returns None for anything not in the set.

    Args:
        location_input: raw location text from the user (city name or ZIP).

    Returns:
        DENVER_JURISDICTION_ID on a hit; None on a miss.
    """
    normalised = location_input.strip().lower()
    if not normalised:
        return None
    if normalised in _CITY_NAME_ALIASES:
        return DENVER_JURISDICTION_ID
    if normalised in _DENVER_ZIPS:
        return DENVER_JURISDICTION_ID
    return None
