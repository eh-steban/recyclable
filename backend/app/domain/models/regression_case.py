"""Domain model for regression / eval cases."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.rule import AcceptedStatus, Disposition


class RegressionCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    query: str
    jurisdiction_id: uuid.UUID
    expected_material_id: uuid.UUID | None = None
    expected_status: AcceptedStatus
    expected_disposition: Disposition
    must_cite_source: bool = True
    refusal_required: bool = False
    notes: str | None = None
