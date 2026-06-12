"""SourceRepo port (Protocol)."""

from typing import Protocol

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.source import SourceDocument, SourceId
from src.domain.shared.repo import Repo


class SourceRepo(Repo[SourceDocument, SourceId], Protocol):
    def find_for_jurisdiction(
        self, jurisdiction_id: JurisdictionId
    ) -> list[SourceDocument]: ...
