"""Rule entity and its typed identity Value."""

import uuid
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.material import MaterialId
from src.domain.knowledge_base.source import SourceId

# ---------------------------------------------------------------------------
# Typed identity Value
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuleId:
    """Typed identity Value for Rule."""

    value: uuid.UUID

    def __str__(self) -> str:
        return str(self.value)


# ---------------------------------------------------------------------------
# Standard Types
# ---------------------------------------------------------------------------


class Disposition(StrEnum):
    CURBSIDE_RECYCLE = "curbside_recycle"
    DROPOFF = "dropoff"
    COMPOST = "compost"
    LANDFILL = "landfill"
    HAZARDOUS_WASTE = "hazardous_waste"
    DONATE = "donate"
    UNKNOWN = "unknown"


class AcceptedStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Rule:
    """Rule aggregate root.

    Encodes a recycling rule for a specific (jurisdiction, material) tuple.
    References other aggregates by typed id -- never by object reference
    (aggregates.md Principle 4).

    INV-AUTH-002: only rules with superseded_by=None are current.
    INV-DATA-002: at most one current rule per (jurisdiction, material).
    """

    id: RuleId
    jurisdiction_id: JurisdictionId
    material_id: MaterialId
    disposition: Disposition
    accepted_status: AcceptedStatus
    source_document_id: SourceId
    source_quote: str
    preparation_steps: tuple[str, ...] = field(default_factory=tuple)
    exceptions: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    confidence: Confidence = Confidence.HIGH
    effective_from: date | None = None
    superseded_by: RuleId | None = None

    def __post_init__(self) -> None:
        if not self.source_quote:
            raise ValueError("source_quote must be non-empty")
