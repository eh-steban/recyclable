"""In-memory implementation of RuleRepo for tests."""

import uuid

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.material import MaterialId
from src.domain.knowledge_base.rule import Rule, RuleId


class MemRuleRepo:
    """Dict-backed RuleRepo satisfying the domain Protocol."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, Rule] = {}

    def next_identity(self) -> RuleId:
        return RuleId(uuid.uuid4())

    def save(self, rule: Rule) -> None:
        self._store[rule.id.value] = rule

    def find_by_id(self, rule_id: RuleId) -> Rule | None:
        return self._store.get(rule_id.value)

    def find_for_jurisdiction(
        self, jurisdiction_id: JurisdictionId
    ) -> list[Rule]:
        """Return all active rules for a jurisdiction."""
        return [
            r
            for r in self._store.values()
            if (
                r.jurisdiction_id == jurisdiction_id and r.superseded_by is None
            )
        ]

    def find_for(
        self,
        jurisdiction_id: JurisdictionId,
        material_id: MaterialId,
    ) -> list[Rule]:
        """Return active rules for exact (jurisdiction, material) tuple.

        Filters to superseded_by is None, sorts by effective_from DESC
        (None last), returns all matches (mirrors the SQL LIMIT 1 intent
        but exposes all so tests can verify uniqueness if needed).
        """
        active = [
            r
            for r in self._store.values()
            if (
                r.jurisdiction_id == jurisdiction_id
                and r.material_id == material_id
                and r.superseded_by is None
            )
        ]
        # Sort by effective_from descending; None sorts last.
        return sorted(
            active,
            key=lambda r: (
                r.effective_from is None,
                # For non-None dates, negate for descending order by
                # converting to ordinal (date is comparable).
                -(r.effective_from.toordinal() if r.effective_from else 0),
            ),
        )
