"""Jurisdiction entity and its typed identity Value."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import override

# ---------------------------------------------------------------------------
# Typed identity Values
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class JurisdictionId:
    """Typed identity Value for Jurisdiction.

    Wraps a UUID so the type checker catches wrong-id-passed bugs at
    compile time (e.g. passing a MaterialId where a JurisdictionId is
    expected).
    """

    value: uuid.UUID

    @override
    def __str__(self) -> str:
        return str(self.value)


# ---------------------------------------------------------------------------
# Enumerations (Standard Types, per value-objects.md Principle 6)
# ---------------------------------------------------------------------------


class JurisdictionType(StrEnum):
    CITY = "city"
    COUNTY = "county"
    STATE = "state"


class SupportedStatus(StrEnum):
    SUPPORTED = "supported"
    COMING_SOON = "coming_soon"
    UNSUPPORTED = "unsupported"


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Jurisdiction:
    """Jurisdiction aggregate root (single-entity aggregate at MVP).

    Identity: JurisdictionId (application-generated UUID).
    Cross-entity references go by typed id, never by object reference.
    """

    id: JurisdictionId
    name: str
    slug: str
    type: JurisdictionType
    country: str  # ISO 3166-1 alpha-2
    supported_status: SupportedStatus
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if len(self.country) != 2:  # noqa: PLR2004
            raise ValueError(
                f"country must be a 2-character ISO code, got: {self.country!r}"
            )
        if not self.slug:
            raise ValueError("slug must be non-empty")
        if not self.name:
            raise ValueError("name must be non-empty")
