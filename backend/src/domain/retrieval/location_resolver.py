import uuid
from dataclasses import dataclass

from src.domain.knowledge_base.jurisdiction import JurisdictionId


# Whole Value per ddd/value-objects.md Principle 3.
@dataclass(frozen=True, slots=True)
class ResolvedJurisdiction:
    """Result of a successful location resolution.

    Carries the typed JurisdictionId alongside the jurisdiction's display
    name so call sites need not re-derive the name from the id. Value
    equality over both attributes (value-objects.md).

    Args:
        jurisdiction_id: typed identity Value for the matched jurisdiction.
        name: display name from the seed data (e.g. "City and County of
            Denver"), suitable for the wire Answer.jurisdiction.name field.
    """

    jurisdiction_id: JurisdictionId
    name: str


#: Sentinel UUID for Denver. Must match
#: backend/seeds/denver-easy/jurisdiction.yaml.
#: See private/specs/01-sonnet-user-path.md § Location resolver (Assumptions).
DENVER_JURISDICTION_ID = JurisdictionId(
    uuid.UUID("00000000-0000-0000-0000-000000000001")
)

#: Pre-built ResolvedJurisdiction for Denver, combining the sentinel UUID
#: and the canonical display name from seeds/denver-easy/jurisdiction.yaml.
DENVER = ResolvedJurisdiction(
    jurisdiction_id=DENVER_JURISDICTION_ID,
    name="City and County of Denver",
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


def resolve_location(
    location_input: str,
) -> ResolvedJurisdiction | None:
    """Resolve a user-supplied location string to a ResolvedJurisdiction.

    Case-insensitive, whitespace-trimmed match against the Denver alias
    set. Returns None for anything not in the set.

    Args:
        location_input: raw location text from the user (city name or ZIP).

    Returns:
        DENVER on a hit (carrying both the JurisdictionId and display
        name); None on a miss.
    """
    normalised = location_input.strip().lower()
    if not normalised:
        return None
    if normalised in _CITY_NAME_ALIASES:
        return DENVER
    if normalised in _DENVER_ZIPS:
        return DENVER
    return None
