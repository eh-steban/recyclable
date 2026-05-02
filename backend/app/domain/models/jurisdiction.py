"""Domain model for jurisdictions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class JurisdictionType(StrEnum):
    CITY = "city"
    COUNTY = "county"
    STATE = "state"


class SupportedStatus(StrEnum):
    SUPPORTED = "supported"
    COMING_SOON = "coming_soon"
    UNSUPPORTED = "unsupported"


class Jurisdiction(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    slug: str
    type: JurisdictionType
    country: str = Field(min_length=2, max_length=2)
    supported_status: SupportedStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
