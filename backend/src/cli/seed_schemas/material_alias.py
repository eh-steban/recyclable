"""Pydantic schemas for seed-parsing material aliases.

These are CLI/parse-layer types, not domain types. They hold the
Pydantic-based shape used to parse and validate YAML seed data before
it is written to the database.
"""

import uuid
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class MaterialAlias(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    material_id: uuid.UUID
    alias: str
    weight: int = 1
