"""Wire schemas for SEO page endpoints.

Shapes per private/specs/contracts/jurisdiction-page.md.
"""

from pydantic import BaseModel

from src.api.schemas.answer import CitationWire

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------


class JurisdictionWire(BaseModel):
    """Jurisdiction shape for SEO pages.

    Richer than JurisdictionRefWire from answer.md: includes slug for
    in-page link construction.
    """

    id: str
    name: str
    slug: str


# ---------------------------------------------------------------------------
# JurisdictionPage
# ---------------------------------------------------------------------------


class MaterialSummaryWire(BaseModel):
    """List element in JurisdictionPage.materials."""

    id: str
    slug: str
    canonical_name: str
    accepted_status: str  # 'accepted' | 'rejected' | 'conditional' | 'unknown'
    needs_preparation: bool
    citation: CitationWire


class JurisdictionPageWire(BaseModel):
    """Response body for GET /pages/jurisdiction/{slug}."""

    jurisdiction: JurisdictionWire
    materials: list[MaterialSummaryWire]


# ---------------------------------------------------------------------------
# MaterialPage
# ---------------------------------------------------------------------------


class MaterialDetailWire(BaseModel):
    """Material identity block for the material page."""

    id: str
    slug: str
    canonical_name: str


class RuleWire(BaseModel):
    """Rule block for the material page.

    Shaped to the page's use case, not to the full rules row.
    """

    disposition: str
    accepted_status: str
    preparation_steps: list[str]
    exceptions: list[str]
    warnings: list[str]


class MaterialPageWire(BaseModel):
    """Response body for GET /pages/jurisdiction/{j}/material/{m}."""

    jurisdiction: JurisdictionWire
    material: MaterialDetailWire
    rule: RuleWire
    citations: list[CitationWire]
