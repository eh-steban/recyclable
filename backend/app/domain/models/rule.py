"""Domain model for recycling rules."""

from __future__ import annotations

import uuid
from datetime import date
from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


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


class Rule(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    jurisdiction_id: uuid.UUID
    material_id: uuid.UUID
    disposition: Disposition
    accepted_status: AcceptedStatus
    preparation_steps: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_document_id: uuid.UUID
    source_quote: str
    confidence: Confidence = Confidence.HIGH
    effective_from: date | None = None
    superseded_by: uuid.UUID | None = None
