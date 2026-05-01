"""Domain model for material aliases."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class MaterialAlias(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    material_id: uuid.UUID
    alias: str
    weight: int = 1
