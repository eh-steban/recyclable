"""RuleRepo port (Protocol).

find_for() implements exact-tuple match for INV-PROD-002:
no cross-jurisdiction fallback, no cross-material fallback.
"""

from typing import Protocol

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.material import MaterialId
from src.domain.knowledge_base.rule import Rule, RuleId
from src.domain.shared.repo import Repo


class RuleRepo(Repo[Rule, RuleId], Protocol):
    def find_for(
        self,
        jurisdiction_id: JurisdictionId,
        material_id: MaterialId,
    ) -> list[Rule]:
        """Return current rules for an exact (jurisdiction, material) tuple.

        Returns only rules with superseded_by IS NULL (INV-AUTH-002).
        """
        ...

    def find_for_jurisdiction(
        self, jurisdiction_id: JurisdictionId
    ) -> list[Rule]:
        """Return all current rules for a jurisdiction.

        Returns only rules with superseded_by IS NULL (INV-AUTH-002).
        Used by SEO page use cases to enumerate the active material set
        for a jurisdiction without iterating over all materials.
        """
        ...
