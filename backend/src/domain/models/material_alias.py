"""Domain model for material aliases."""

from __future__ import annotations

import uuid
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class MaterialAlias(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    material_id: uuid.UUID
    alias: str
    weight: int = 1
