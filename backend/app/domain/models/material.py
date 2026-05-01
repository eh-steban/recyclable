"""Domain model for materials."""
from __future__ import annotations

import uuid
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MaterialCategory(StrEnum):
    GLASS = "glass"
    PLASTIC = "plastic"
    METAL = "metal"
    PAPER = "paper"
    ORGANIC = "organic"
    HAZARDOUS = "hazardous"
    ELECTRONIC = "electronic"
    TEXTILE = "textile"
    OTHER = "other"


class Material(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    canonical_name: str
    slug: str
    category: MaterialCategory
    parent_id: uuid.UUID | None = None
