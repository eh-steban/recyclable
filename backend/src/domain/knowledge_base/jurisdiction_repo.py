"""JurisdictionRepo port (Protocol).

The interface lives in domain/ alongside the aggregate it addresses.
The implementation lives in infra/db/repos/.
"""

from typing import Protocol

from src.domain.knowledge_base.jurisdiction import Jurisdiction, JurisdictionId


class JurisdictionRepo(Protocol):
    """Repo port for Jurisdiction aggregate.

    Persistence-oriented style: callers explicitly call save().
    next_identity() mints a fresh id before construction.
    """

    def next_identity(self) -> JurisdictionId: ...

    def save(self, jurisdiction: Jurisdiction) -> None: ...

    def find_by_id(
        self, jurisdiction_id: JurisdictionId
    ) -> Jurisdiction | None: ...

    def find_by_slug(self, slug: str) -> Jurisdiction | None: ...
