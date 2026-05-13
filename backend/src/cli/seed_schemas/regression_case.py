"""Pydantic schemas for seed-parsing regression cases.

These are CLI/parse-layer types, not domain types. They hold the
Pydantic-based shape used to parse and validate YAML seed data before
it is written to the database.
"""

import uuid
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from src.cli.seed_schemas.rule import AcceptedStatus, Disposition


class RegressionCase(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    query: str
    jurisdiction_id: uuid.UUID
    expected_material_id: uuid.UUID | None = None
    expected_status: AcceptedStatus
    expected_disposition: Disposition
    must_cite_source: bool = True
    refusal_required: bool = False
    notes: str | None = None
