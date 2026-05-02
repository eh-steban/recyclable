"""Domain model for LLM answer traces."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnswerTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_query: str
    jurisdiction_id: uuid.UUID | None = None
    normalized_materials: list[uuid.UUID] = Field(default_factory=list)
    retrieved_rule_ids: list[uuid.UUID] = Field(default_factory=list)
    retrieved_source_ids: list[uuid.UUID] = Field(default_factory=list)
    prompt_name: str
    prompt_version: int
    model_id: str
    raw_model_output: dict[str, Any] = Field(default_factory=dict)
    final_answer: dict[str, Any] = Field(default_factory=dict)
    validator_result: dict[str, Any] = Field(default_factory=dict)
    confidence: str | None = None
    latency_ms: int | None = None
    cache_hit: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
