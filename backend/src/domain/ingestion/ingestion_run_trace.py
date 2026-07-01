"""IngestionRunTrace entity.

Minimal trace entity for Story 1: minted at run start to satisfy the
non-null FK on IngestionReport. Full enrichment (tool_calls, urls_fetched,
etc.) is Story 4.

Architecture note: IngestionRunTrace is an Entity (not a Value) because it
has a managed lifecycle -- created once at run start, potentially enriched
by later stories. It lives in the audit Module per architecture.md
(ingestion audit records live alongside AnswerAuditRecord).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import override


@dataclass(frozen=True, slots=True)
class IngestionRunTraceId:
    """Typed identity Value for IngestionRunTrace."""

    value: uuid.UUID

    @override
    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class IngestionRunTrace:
    """Minimal ingestion run trace entity.

    Fields:
        id: typed identity, minted by repo.next_identity() at run start.
        seed_url: the URL the run was seeded with.
        created_at: UTC timestamp when the trace was created.
    """

    id: IngestionRunTraceId
    seed_url: str
    created_at: datetime
