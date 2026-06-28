"""JurisdictionRepo port (Protocol)."""

from typing import Protocol

from src.domain.knowledge_base.jurisdiction import Jurisdiction, JurisdictionId
from src.domain.shared.repo import Repo


class JurisdictionRepo(Repo[Jurisdiction, JurisdictionId], Protocol):
    def find_by_slug(self, slug: str) -> Jurisdiction | None: ...
