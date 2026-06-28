"""Full-wire syrupy golden for GetMaterialPage.execute().

Asserts the entire MaterialPageWire over a deterministic-UUID fixture
that includes a superseded rule, pinning INV-AUTH-002: the superseded rule
must be absent from the output.

The active rule carries non-trivial preparation_steps, exceptions, and
warnings so those lists are non-empty in the golden.
"""

import uuid

import pytest
from syrupy.assertion import SnapshotAssertion

from src.application.get_material_page import GetMaterialPage
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.material import MaterialId
from src.domain.knowledge_base.rule import (
    AcceptedStatus,
    Disposition,
    RuleId,
)
from src.domain.knowledge_base.source import SourceId
from tests.utils.builders import (
    make_jurisdiction,
    make_material,
    make_rule,
    make_source_document,
)
from tests.utils.fakes.jurisdiction_repo import MemJurisdictionRepo
from tests.utils.fakes.material_repo import MemMaterialRepo
from tests.utils.fakes.rule_repo import MemRuleRepo
from tests.utils.fakes.source_repo import MemSourceRepo

# ---------------------------------------------------------------------------
# Sentinel UUIDs -- fixed so model_dump() is byte-stable across seeds.
# ---------------------------------------------------------------------------

_JID = JurisdictionId(uuid.UUID("00000000-0000-0000-0000-000000000001"))
_MID = MaterialId(uuid.UUID("00000000-0000-0000-0000-000000000002"))
_SID = SourceId(uuid.UUID("00000000-0000-0000-0000-000000000010"))
_RID_ACTIVE = RuleId(uuid.UUID("00000000-0000-0000-0000-000000000020"))
_RID_SUPERSEDED = RuleId(uuid.UUID("00000000-0000-0000-0000-000000000030"))


@pytest.fixture()
def seeded_repos(
    mem_jurisdiction_repo: MemJurisdictionRepo,
    mem_material_repo: MemMaterialRepo,
    mem_rule_repo: MemRuleRepo,
    mem_source_repo: MemSourceRepo,
) -> tuple[
    MemJurisdictionRepo,
    MemMaterialRepo,
    MemRuleRepo,
    MemSourceRepo,
]:
    jurisdiction = make_jurisdiction(
        id=_JID,
        name="City and County of Denver",
        slug="denver-co-us",
    )
    material = make_material(
        id=_MID,
        slug="cardboard",
        canonical_name="Cardboard",
    )
    source = make_source_document(
        id=_SID,
        jurisdiction_id=_JID,
        url="https://denvergov.org/recycling/accepted",
        title="Denver Accepted-for-Recycling",
    )
    active_rule = make_rule(
        id=_RID_ACTIVE,
        jurisdiction_id=_JID,
        material_id=_MID,
        source_document_id=_SID,
        disposition=Disposition.CURBSIDE_RECYCLE,
        accepted_status=AcceptedStatus.ACCEPTED,
        source_quote="Cardboard is accepted curbside when flattened.",
        preparation_steps=("Flatten the box", "Remove tape and staples"),
        exceptions=("Waxed cardboard is not accepted",),
        warnings=("Keep dry -- wet cardboard goes to landfill",),
    )
    superseded_rule = make_rule(
        id=_RID_SUPERSEDED,
        jurisdiction_id=_JID,
        material_id=_MID,
        source_document_id=_SID,
        disposition=Disposition.LANDFILL,
        accepted_status=AcceptedStatus.REJECTED,
        source_quote="Old rule: cardboard is not recyclable -- landfill only.",
        superseded_by=_RID_ACTIVE,
    )

    mem_jurisdiction_repo.save(jurisdiction)
    mem_material_repo.save(material)

    # Superseded first: if find_for's filter broke, dict iteration order
    # would yield superseded_rule before active_rule, stable-sort preserves
    # that order (both have effective_from=None), and rules[0] would be the
    # superseded rule -- changing the amber.
    mem_rule_repo.save(superseded_rule)
    mem_rule_repo.save(active_rule)

    mem_source_repo.save(source)

    return (
        mem_jurisdiction_repo,
        mem_material_repo,
        mem_rule_repo,
        mem_source_repo,
    )


class TestGetMaterialPageGolden:
    def test_golden(
        self,
        seeded_repos: tuple[
            MemJurisdictionRepo,
            MemMaterialRepo,
            MemRuleRepo,
            MemSourceRepo,
        ],
        snapshot: SnapshotAssertion,
    ) -> None:
        jurisdiction_repo, material_repo, rule_repo, source_repo = seeded_repos
        use_case = GetMaterialPage(
            jurisdiction_repo=jurisdiction_repo,
            material_repo=material_repo,
            rule_repo=rule_repo,
            source_repo=source_repo,
        )

        page = use_case.execute("denver-co-us", "cardboard")
        assert page is not None

        assert page.model_dump() == snapshot(name="material_page_wire")
