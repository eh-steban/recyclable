"""Builders for knowledge-base aggregates.

Relations are threaded by passing a shared typed id (mint a jurisdiction,
then pass its id into make_rule / make_source_document); when an id is
omitted a fresh one is minted so standalone construction stays trivial.
"""

import uuid
from datetime import UTC, date, datetime

from src.domain.knowledge_base.jurisdiction import (
    Jurisdiction,
    JurisdictionId,
    JurisdictionType,
    SupportedStatus,
)
from src.domain.knowledge_base.material import (
    Material,
    MaterialCategory,
    MaterialId,
)
from src.domain.knowledge_base.rule import (
    AcceptedStatus,
    Confidence,
    Disposition,
    Rule,
    RuleId,
)
from src.domain.knowledge_base.source import SourceDocument, SourceId

# Mirror of src.domain.retrieval.location_resolver.DENVER_SLUG, inlined so the
# knowledge_base builders do not import the retrieval module. The location
# resolver maps "Denver" to this slug, so a jurisdiction built with the default
# is found by the slug lookups the user-path tests drive.
_DENVER_SLUG = "denver-co-us"


def make_jurisdiction(
    *,
    id: JurisdictionId | None = None,
    name: str = "City and County of Denver",
    slug: str = _DENVER_SLUG,
    type: JurisdictionType = JurisdictionType.CITY,
    country: str = "US",
    supported_status: SupportedStatus = SupportedStatus.SUPPORTED,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Jurisdiction:
    now = datetime.now(tz=UTC)
    return Jurisdiction(
        id=id or JurisdictionId(uuid.uuid4()),
        name=name,
        slug=slug,
        type=type,
        country=country,
        supported_status=supported_status,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


def make_material(
    *,
    id: MaterialId | None = None,
    slug: str = "cardboard",
    canonical_name: str | None = None,
    category: MaterialCategory = MaterialCategory.PAPER,
    parent_id: MaterialId | None = None,
) -> Material:
    return Material(
        id=id or MaterialId(uuid.uuid4()),
        canonical_name=canonical_name or slug.replace("-", " ").title(),
        slug=slug,
        category=category,
        parent_id=parent_id,
    )


def make_rule(
    *,
    id: RuleId | None = None,
    jurisdiction_id: JurisdictionId | None = None,
    material_id: MaterialId | None = None,
    source_document_id: SourceId | None = None,
    disposition: Disposition = Disposition.CURBSIDE_RECYCLE,
    accepted_status: AcceptedStatus = AcceptedStatus.ACCEPTED,
    source_quote: str = "Cardboard is accepted curbside.",
    preparation_steps: tuple[str, ...] = (),
    exceptions: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    confidence: Confidence = Confidence.HIGH,
    effective_from: date | None = None,
    superseded_by: RuleId | None = None,
) -> Rule:
    return Rule(
        id=id or RuleId(uuid.uuid4()),
        jurisdiction_id=jurisdiction_id or JurisdictionId(uuid.uuid4()),
        material_id=material_id or MaterialId(uuid.uuid4()),
        source_document_id=source_document_id or SourceId(uuid.uuid4()),
        disposition=disposition,
        accepted_status=accepted_status,
        source_quote=source_quote,
        preparation_steps=preparation_steps,
        exceptions=exceptions,
        warnings=warnings,
        confidence=confidence,
        effective_from=effective_from,
        superseded_by=superseded_by,
    )


def make_source_document(
    *,
    id: SourceId | None = None,
    jurisdiction_id: JurisdictionId | None = None,
    url: str = "https://denvergov.org/recycling",
    title: str = "Denver Recycling Guide",
    authority_level: int = 1,
    fetched_at: datetime | None = None,
    source_text: str = "Cardboard is accepted curbside.",
    source_text_hash: str = "hash",
    effective_date: date | None = None,
    last_reviewed_at: datetime | None = None,
) -> SourceDocument:
    return SourceDocument(
        id=id or SourceId(uuid.uuid4()),
        jurisdiction_id=jurisdiction_id or JurisdictionId(uuid.uuid4()),
        url=url,
        title=title,
        authority_level=authority_level,
        fetched_at=fetched_at or datetime.now(tz=UTC),
        source_text=source_text,
        source_text_hash=source_text_hash,
        effective_date=effective_date,
        last_reviewed_at=last_reviewed_at,
    )
