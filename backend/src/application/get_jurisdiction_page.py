"""GetJurisdictionPage use case -- SEO landing page for a jurisdiction.

Composes Jurisdiction, Material, Rule, and Source via their repo ports.
Shaped to the page use case per integrating-bounded-contexts.md Principle 4.
Superseded rules (superseded_by IS NOT NULL) are excluded (INV-AUTH-002).

MaterialSummary selection:
  - accepted_status taken from the active Rule.accepted_status.
  - needs_preparation: True when active rule.preparation_steps is non-empty.
  - citation: lowest-authority-level SourceDocument row that backs the rule
    (per jurisdiction-page.md § MaterialSummary). When no source found,
    uses an empty CitationWire.
"""

import logging
from typing import final

from src.api.schemas.answer import CitationWire
from src.api.schemas.jurisdiction_page import (
    JurisdictionPageWire,
    JurisdictionWire,
    MaterialSummaryWire,
)
from src.domain.knowledge_base.jurisdiction_repo import JurisdictionRepo
from src.domain.knowledge_base.material_repo import MaterialRepo
from src.domain.knowledge_base.rule_repo import RuleRepo
from src.domain.knowledge_base.source_repo import SourceRepo

logger = logging.getLogger(__name__)


@final
class GetJurisdictionPage:
    """Fetch and compose the SEO jurisdiction landing page."""

    def __init__(
        self,
        jurisdiction_repo: JurisdictionRepo,
        material_repo: MaterialRepo,
        rule_repo: RuleRepo,
        source_repo: SourceRepo,
    ) -> None:
        self._jurisdiction_repo = jurisdiction_repo
        self._material_repo = material_repo
        self._rule_repo = rule_repo
        self._source_repo = source_repo

    def execute(self, slug: str) -> JurisdictionPageWire | None:
        """Return the jurisdiction page or None when slug not found."""
        jurisdiction = self._jurisdiction_repo.find_by_slug(slug)
        if jurisdiction is None:
            logger.info("GetJurisdictionPage: slug=%r not found", slug)
            return None

        # Fetch all active rules for this jurisdiction (INV-AUTH-002:
        # find_for_jurisdiction returns only superseded_by IS NULL).
        rules = self._rule_repo.find_for_jurisdiction(jurisdiction.id)
        logger.debug(
            "GetJurisdictionPage: jid=%s active_rules=%d",
            jurisdiction.id,
            len(rules),
        )

        materials: list[MaterialSummaryWire] = []
        for rule in rules:
            material = self._material_repo.find_by_id(rule.material_id)
            if material is None:
                logger.warning(
                    "GetJurisdictionPage: rule %s references missing "
                    "material %s -- skipping",
                    rule.id,
                    rule.material_id,
                )
                continue

            source = self._source_repo.find_by_id(rule.source_document_id)
            if source is not None:
                citation = CitationWire(
                    title=source.title,
                    url=source.url,
                    quote=rule.source_quote[:200]
                    if rule.source_quote
                    else None,
                )
            else:
                citation = CitationWire(title="", url="", quote=None)

            materials.append(
                MaterialSummaryWire(
                    id=str(material.id.value),
                    slug=material.slug,
                    canonical_name=material.canonical_name,
                    accepted_status=rule.accepted_status.value,
                    needs_preparation=bool(rule.preparation_steps),
                    citation=citation,
                )
            )

        return JurisdictionPageWire(
            jurisdiction=JurisdictionWire(
                id=str(jurisdiction.id.value),
                name=jurisdiction.name,
                slug=jurisdiction.slug,
            ),
            materials=materials,
        )
