"""Domain model for LLM answer traces."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

# JSON-compatible dict: str keys, values are primitive scalars or nested
# JSON structures.  Using object avoids `Any` while remaining broad enough
# for arbitrary JSONB payloads.
JsonDict = dict[str, object]


class AnswerTrace(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_query: str
    jurisdiction_id: uuid.UUID | None = None
    normalized_materials: list[uuid.UUID] = Field(default_factory=list)
    retrieved_rule_ids: list[uuid.UUID] = Field(default_factory=list)
    retrieved_source_ids: list[uuid.UUID] = Field(default_factory=list)
    prompt_name: str
    prompt_version: int
    model_id: str
    raw_model_output: JsonDict = Field(default_factory=dict)
    final_answer: JsonDict = Field(default_factory=dict)
    validator_result: JsonDict = Field(default_factory=dict)
    confidence: str | None = None
    latency_ms: int | None = None
    cache_hit: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
