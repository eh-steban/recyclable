"""In-memory implementation of SourceRepo for tests."""

import uuid
from typing import override

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.source import SourceDocument, SourceId
from tests.utils.fakes._base import InMemoryRepo


class MemSourceRepo(InMemoryRepo[SourceDocument, SourceId]):
    @override
    def next_identity(self) -> SourceId:
        return SourceId(uuid.uuid4())

    def find_for_jurisdiction(
        self, jurisdiction_id: JurisdictionId
    ) -> list[SourceDocument]:
        return [
            s
            for s in self._store.values()
            if s.jurisdiction_id == jurisdiction_id
        ]
