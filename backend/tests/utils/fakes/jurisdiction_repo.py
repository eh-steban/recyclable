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
