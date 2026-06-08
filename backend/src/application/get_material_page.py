"""GetMaterialPage use case -- SEO material detail page.

Composes Jurisdiction, Material, Rule, and Source via their repo ports.
Shaped to the material page use case per jurisdiction-page.md contract.
Superseded rules excluded via RuleRepo.find_for() (INV-AUTH-002).
"""

import logging
from typing import final

from src.api.schemas.answer import CitationWire
from src.api.schemas.jurisdiction_page import (
    JurisdictionWire,
    MaterialDetailWire,
    MaterialPageWire,
    RuleWire,
)
from src.domain.knowledge_base.jurisdiction_repo import JurisdictionRepo
from src.domain.knowledge_base.material_repo import MaterialRepo
from src.domain.knowledge_base.rule_repo import RuleRepo
from src.domain.knowledge_base.source_repo import SourceRepo

logger = logging.getLogger(__name__)


@final
class GetMaterialPage:
    """Fetch and compose the SEO material detail page."""

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

    def execute(
        self, jurisdiction_slug: str, material_slug: str
    ) -> MaterialPageWire | None:
        """Return the material page or None when either slug not found."""
        jurisdiction = self._jurisdiction_repo.find_by_slug(jurisdiction_slug)
        if jurisdiction is None:
            logger.info(
                "GetMaterialPage: jurisdiction slug=%r not found",
                jurisdiction_slug,
            )
            return None

        material = self._material_repo.find_by_slug(material_slug)
        if material is None:
            logger.info(
                "GetMaterialPage: material slug=%r not found", material_slug
            )
            return None

        # find_for returns only superseded_by IS NULL (INV-AUTH-002).
        rules = self._rule_repo.find_for(jurisdiction.id, material.id)
        if not rules:
            logger.info(
                "GetMaterialPage: no active rule for jid=%s mid=%s",
                jurisdiction.id,
                material.id,
            )
            return None

        # Take the first (most recent by effective_from) active rule.
        rule = rules[0]

        source = self._source_repo.find_by_id(rule.source_document_id)
        citations: list[CitationWire] = []
        if source is not None:
            citations.append(
                CitationWire(
                    title=source.title,
                    url=source.url,
                    quote=rule.source_quote[:200]
                    if rule.source_quote
                    else None,
                )
            )

        return MaterialPageWire(
            jurisdiction=JurisdictionWire(
                id=str(jurisdiction.id.value),
                name=jurisdiction.name,
                slug=jurisdiction.slug,
            ),
            material=MaterialDetailWire(
                id=str(material.id.value),
                slug=material.slug,
                canonical_name=material.canonical_name,
            ),
            rule=RuleWire(
                disposition=rule.disposition.value,
                accepted_status=rule.accepted_status.value,
                preparation_steps=list(rule.preparation_steps),
                exceptions=list(rule.exceptions),
                warnings=list(rule.warnings),
            ),
            citations=citations,
        )
