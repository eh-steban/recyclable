"""In-memory implementation of RuleRepo for tests."""

import uuid
from typing import override

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.material import MaterialId
from src.domain.knowledge_base.rule import Rule, RuleId
from tests.utils.fakes._base import InMemoryRepo


class MemRuleRepo(InMemoryRepo[Rule, RuleId]):
    @override
    def next_identity(self) -> RuleId:
        return RuleId(uuid.uuid4())

    def find_for_jurisdiction(
        self, jurisdiction_id: JurisdictionId
    ) -> list[Rule]:
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
        # The real repo applies LIMIT 1; the fake returns all matches
        # (sorted effective_from DESC, None last) so tests can assert
        # uniqueness.
        active = [
            r
            for r in self._store.values()
            if (
                r.jurisdiction_id == jurisdiction_id
                and r.material_id == material_id
                and r.superseded_by is None
            )
        ]
        return sorted(
            active,
            key=lambda r: (
                r.effective_from is None,
                -(r.effective_from.toordinal() if r.effective_from else 0),
            ),
        )
