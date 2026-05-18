"""In-memory implementation of SourceRepo for tests."""

import uuid

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.source import SourceDocument, SourceId


class MemSourceRepo:
    """Dict-backed SourceRepo satisfying the domain Protocol."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, SourceDocument] = {}

    def next_identity(self) -> SourceId:
        return SourceId(uuid.uuid4())

    def save(self, source: SourceDocument) -> None:
        self._store[source.id.value] = source

    def find_by_id(self, source_id: SourceId) -> SourceDocument | None:
        return self._store.get(source_id.value)

    def find_for_jurisdiction(
        self, jurisdiction_id: JurisdictionId
    ) -> list[SourceDocument]:
        return [
            s
            for s in self._store.values()
            if s.jurisdiction_id == jurisdiction_id
        ]
