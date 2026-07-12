"""In-memory implementation of JurisdictionRepo for tests."""

import uuid
from typing import override

from src.domain.knowledge_base.jurisdiction import Jurisdiction, JurisdictionId
from tests.utils.fakes._base import InMemoryRepo


class MemJurisdictionRepo(InMemoryRepo[Jurisdiction, JurisdictionId]):
    @override
    def next_identity(self) -> JurisdictionId:
        return JurisdictionId(uuid.uuid4())

    def find_by_slug(self, slug: str) -> Jurisdiction | None:
        return next((j for j in self._store.values() if j.slug == slug), None)

    def search_by_name(self, query: str) -> list[Jurisdiction]:
        needle = query.lower()
        return sorted(
            (j for j in self._store.values() if needle in j.name.lower()),
            key=lambda j: j.name,
        )
