"""Full-wire syrupy golden for GetJurisdictionPage.execute().

Asserts the entire JurisdictionPageWire over a deterministic-UUID fixture
that includes a superseded rule, pinning INV-AUTH-002: the superseded rule
must be absent from the output.

Also exercises the empty-CitationWire branch (glass rule whose
source_document_id has no matching SourceDocument in the repo).
"""

import uuid

import pytest
from syrupy.assertion import SnapshotAssertion

from src.application.get_jurisdiction_page import GetJurisdictionPage
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
_MID_CARDBOARD = MaterialId(uuid.UUID("00000000-0000-0000-0000-000000000002"))
_MID_GLASS = MaterialId(uuid.UUID("00000000-0000-0000-0000-000000000003"))
_SID_CARDBOARD = SourceId(uuid.UUID("00000000-0000-0000-0000-000000000010"))
# _SID_GLASS is intentionally NOT saved in the source repo --
# exercises the empty-CitationWire branch in GetJurisdictionPage.
_SID_GLASS_MISSING = SourceId(uuid.UUID("00000000-0000-0000-0000-000000000011"))
_RID_ACTIVE_CARDBOARD = RuleId(
    uuid.UUID("00000000-0000-0000-0000-000000000020")
)
_RID_ACTIVE_GLASS = RuleId(uuid.UUID("00000000-0000-0000-0000-000000000021"))
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

    cardboard = make_material(
        id=_MID_CARDBOARD,
        slug="cardboard",
        canonical_name="Cardboard",
    )
    glass = make_material(
        id=_MID_GLASS,
        slug="glass-bottles",
        canonical_name="Glass Bottles",
    )

    source_cardboard = make_source_document(
        id=_SID_CARDBOARD,
        jurisdiction_id=_JID,
        url="https://denvergov.org/recycling/accepted",
        title="Denver Accepted-for-Recycling",
    )

    active_cardboard = make_rule(
        id=_RID_ACTIVE_CARDBOARD,
        jurisdiction_id=_JID,
        material_id=_MID_CARDBOARD,
        source_document_id=_SID_CARDBOARD,
        disposition=Disposition.CURBSIDE_RECYCLE,
        accepted_status=AcceptedStatus.ACCEPTED,
        source_quote="Cardboard is accepted curbside when flattened.",
        preparation_steps=("Flatten the box",),
    )
    active_glass = make_rule(
        id=_RID_ACTIVE_GLASS,
        jurisdiction_id=_JID,
        material_id=_MID_GLASS,
        source_document_id=_SID_GLASS_MISSING,
        disposition=Disposition.DROPOFF,
        accepted_status=AcceptedStatus.CONDITIONAL,
        source_quote="Glass bottles must be dropped off at a collection site.",
    )
    # Superseded rule: visibly different disposition/status/quote so any
    # regression that leaked it would change the golden (INV-AUTH-002).
    superseded_cardboard = make_rule(
        id=_RID_SUPERSEDED,
        jurisdiction_id=_JID,
        material_id=_MID_CARDBOARD,
        source_document_id=_SID_CARDBOARD,
        disposition=Disposition.LANDFILL,
        accepted_status=AcceptedStatus.REJECTED,
        source_quote="Old rule: cardboard is not recyclable -- landfill only.",
        superseded_by=_RID_ACTIVE_CARDBOARD,
    )

    mem_jurisdiction_repo.save(jurisdiction)

    mem_material_repo.save(cardboard)
    mem_material_repo.save(glass)

    mem_rule_repo.save(active_cardboard)
    mem_rule_repo.save(active_glass)
    mem_rule_repo.save(superseded_cardboard)

    mem_source_repo.save(source_cardboard)
    # source for glass intentionally NOT saved -- empty-CitationWire branch.

    return (
        mem_jurisdiction_repo,
        mem_material_repo,
        mem_rule_repo,
        mem_source_repo,
    )


class TestGetJurisdictionPageGolden:
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
        use_case = GetJurisdictionPage(
            jurisdiction_repo=jurisdiction_repo,
            material_repo=material_repo,
            rule_repo=rule_repo,
            source_repo=source_repo,
        )

        page = use_case.execute("denver-co-us")
        assert page is not None

        assert page.model_dump() == snapshot(name="jurisdiction_page_wire")
