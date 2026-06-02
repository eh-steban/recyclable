"""In-memory implementation of MaterialRepo for tests."""

import uuid

from src.domain.knowledge_base.material import (
    Material,
    MaterialAlias,
    MaterialId,
)


class MemMaterialRepo:
    """Dict-backed MaterialRepo satisfying the domain Protocol."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, Material] = {}
        self._aliases: list[MaterialAlias] = []

    def next_identity(self) -> MaterialId:
        return MaterialId(uuid.uuid4())

    def save(self, material: Material) -> None:
        self._store[material.id.value] = material

    def add_alias(self, alias: MaterialAlias) -> None:
        """Helper to attach an alias (not part of the port Protocol)."""
        self._aliases.append(alias)

    def find_by_id(self, material_id: MaterialId) -> Material | None:
        return self._store.get(material_id.value)

    def find_by_slug(self, slug: str) -> Material | None:
        return next((m for m in self._store.values() if m.slug == slug), None)

    def find_aliases_for(self, material_id: MaterialId) -> list[MaterialAlias]:
        return [a for a in self._aliases if a.material_id == material_id]

    def all_materials(self) -> list[Material]:
        return list(self._store.values())
