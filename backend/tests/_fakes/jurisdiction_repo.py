"""In-memory implementation of JurisdictionRepo for tests."""

import uuid

from src.domain.knowledge_base.jurisdiction import Jurisdiction, JurisdictionId


class InMemoryJurisdictionRepo:
    """Dict-backed JurisdictionRepo satisfying the domain Protocol."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, Jurisdiction] = {}

    def next_identity(self) -> JurisdictionId:
        return JurisdictionId(uuid.uuid4())

    def save(self, jurisdiction: Jurisdiction) -> None:
        self._store[jurisdiction.id.value] = jurisdiction

    def find_by_id(
        self, jurisdiction_id: JurisdictionId
    ) -> Jurisdiction | None:
        return self._store.get(jurisdiction_id.value)

    def find_by_slug(self, slug: str) -> Jurisdiction | None:
        return next((j for j in self._store.values() if j.slug == slug), None)
