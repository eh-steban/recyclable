"""SourceRepo port (Protocol)."""

from typing import Protocol

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.source import SourceDocument, SourceId


class SourceRepo(Protocol):
    """Repo port for SourceDocument aggregate."""

    def next_identity(self) -> SourceId: ...

    def save(self, source: SourceDocument) -> None: ...

    def find_by_id(self, source_id: SourceId) -> SourceDocument | None: ...

    def find_for_jurisdiction(
        self, jurisdiction_id: JurisdictionId
    ) -> list[SourceDocument]: ...
