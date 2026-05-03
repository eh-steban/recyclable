"""Domain model for source documents."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class SourceDocument(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    jurisdiction_id: uuid.UUID
    url: str
    title: str
    authority_level: int = Field(ge=1, le=6)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    effective_date: date | None = None
    source_text: str
    source_text_hash: str
    last_reviewed_at: datetime | None = None
