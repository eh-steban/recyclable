"""Pydantic schemas for seed-parsing materials.

These are CLI/parse-layer types, not domain types. They hold the
Pydantic-based shape used to parse and validate YAML seed data before
it is written to the database.
"""

import uuid
from enum import StrEnum
from typing import ClassVar

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
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    canonical_name: str
    slug: str
    category: MaterialCategory
    parent_id: uuid.UUID | None = None
