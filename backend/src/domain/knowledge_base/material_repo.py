"""MaterialRepo port (Protocol)."""

from typing import Protocol

from src.domain.knowledge_base.material import (
    Material,
    MaterialAlias,
    MaterialId,
)
from src.domain.shared.repo import Repo


class MaterialRepo(Repo[Material, MaterialId], Protocol):
    def find_by_slug(self, slug: str) -> Material | None: ...

    def find_aliases_for(
        self, material_id: MaterialId
    ) -> list[MaterialAlias]: ...

    def all_materials(self) -> list[Material]: ...
