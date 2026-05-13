"""MaterialRepo port (Protocol)."""

from typing import Protocol

from src.domain.knowledge_base.material import (
    Material,
    MaterialAlias,
    MaterialId,
)


class MaterialRepo(Protocol):
    """Repo port for Material aggregate."""

    def next_identity(self) -> MaterialId: ...

    def save(self, material: Material) -> None: ...

    def find_by_id(self, material_id: MaterialId) -> Material | None: ...

    def find_by_slug(self, slug: str) -> Material | None: ...

    def find_aliases_for(
        self, material_id: MaterialId
    ) -> list[MaterialAlias]: ...
