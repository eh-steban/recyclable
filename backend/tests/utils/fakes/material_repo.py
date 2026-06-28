"""In-memory implementation of MaterialRepo for tests."""

import uuid
from typing import override

from src.domain.knowledge_base.material import (
    Material,
    MaterialAlias,
    MaterialId,
)
from tests.utils.fakes._base import InMemoryRepo


class MemMaterialRepo(InMemoryRepo[Material, MaterialId]):
    def __init__(self) -> None:
        super().__init__()
        self._aliases: list[MaterialAlias] = []

    @override
    def next_identity(self) -> MaterialId:
        return MaterialId(uuid.uuid4())

    def add_alias(self, alias: MaterialAlias) -> None:
        self._aliases.append(alias)

    def find_by_slug(self, slug: str) -> Material | None:
        return next((m for m in self._store.values() if m.slug == slug), None)

    def find_aliases_for(self, material_id: MaterialId) -> list[MaterialAlias]:
        return [a for a in self._aliases if a.material_id == material_id]

    def all_materials(self) -> list[Material]:
        return list(self._store.values())
