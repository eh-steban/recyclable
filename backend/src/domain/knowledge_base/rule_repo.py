"""RuleRepo port (Protocol).

find_for() implements exact-tuple match for INV-PROD-002:
no cross-jurisdiction fallback, no cross-material fallback.
"""

from typing import Protocol

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.material import MaterialId
from src.domain.knowledge_base.rule import Rule, RuleId


class RuleRepo(Protocol):
    """Repo port for Rule aggregate."""

    def next_identity(self) -> RuleId: ...

    def save(self, rule: Rule) -> None: ...

    def find_by_id(self, rule_id: RuleId) -> Rule | None: ...

    def find_for(
        self,
        jurisdiction_id: JurisdictionId,
        material_id: MaterialId,
    ) -> list[Rule]:
        """Return current rules for an exact (jurisdiction, material) tuple.

        Returns only rules with superseded_by IS NULL (INV-AUTH-002).
        Never falls back to neighbouring jurisdictions or related materials
        (INV-PROD-002).
        """
        ...
