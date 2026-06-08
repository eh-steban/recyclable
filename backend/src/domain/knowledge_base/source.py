"""SourceDocument entity and its typed identity Value."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import override

from src.domain.knowledge_base.jurisdiction import JurisdictionId

# ---------------------------------------------------------------------------
# Typed identity Value
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SourceId:
    """Typed identity Value for SourceDocument."""

    value: uuid.UUID

    @override
    def __str__(self) -> str:
        return str(self.value)


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """Source document aggregate root (single-entity aggregate at MVP).

    Represents an authoritative web page or document from which recycling
    rules are extracted. URLs are immutable once cited (INV-DATA-003).
    """

    id: SourceId
    jurisdiction_id: JurisdictionId
    url: str
    title: str
    authority_level: int  # 1=official municipal ... 6=blog
    fetched_at: datetime
    source_text: str
    source_text_hash: str
    effective_date: date | None = None
    last_reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not (1 <= self.authority_level <= 6):  # noqa: PLR2004
            msg = (
                f"authority_level must be in [1, 6],"
                f" got: {self.authority_level}"
            )
            raise ValueError(msg)
        if not self.url:
            raise ValueError("url must be non-empty")
        if not self.title:
            raise ValueError("title must be non-empty")
