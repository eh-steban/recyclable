"""SEO page routes -- thin HTTP adapters for page use cases.

Per backend/CLAUDE.md § HTTP API conventions: each handler calls
exactly one application service via Depends and maps None -> 404.
No domain imports; no business-logic branches.

Routes per private/specs/contracts/jurisdiction-page.md:
  GET /pages/jurisdiction/{slug}
  GET /pages/jurisdiction/{j_slug}/material/{m_slug}
"""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.deps import (
    get_jurisdiction_page_service,
    get_material_page_service,
)
from src.api.schemas.answer import ErrorEnvelope
from src.api.schemas.jurisdiction_page import (
    JurisdictionPageWire,
    MaterialPageWire,
)
from src.application.get_jurisdiction_page import GetJurisdictionPage
from src.application.get_material_page import GetMaterialPage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pages")

_JURISDICTION_NOT_FOUND_RESPONSE: dict[int | str, dict[str, object]] = {
    404: {
        "model": ErrorEnvelope,
        "description": "not_found -- no jurisdiction for this slug",
    },
}

_MATERIAL_NOT_FOUND_RESPONSE: dict[int | str, dict[str, object]] = {
    404: {
        "model": ErrorEnvelope,
        "description": (
            "not_found -- no jurisdiction or material for these slugs"
        ),
    },
}


@router.get(
    "/jurisdiction/{slug}",
    response_model=JurisdictionPageWire,
    responses=_JURISDICTION_NOT_FOUND_RESPONSE,
)
def get_jurisdiction_page(
    slug: str,
    service: GetJurisdictionPage = Depends(get_jurisdiction_page_service),
) -> JurisdictionPageWire | JSONResponse:
    """Return the SEO jurisdiction landing page or 404 on slug miss."""
    logger.info("get_jurisdiction_page: slug=%r", slug)
    result = service.execute(slug)
    if result is None:
        return JSONResponse(
            status_code=404,
            content={"error": "not_found"},
        )
    return result


@router.get(
    "/jurisdiction/{j_slug}/material/{m_slug}",
    response_model=MaterialPageWire,
    responses=_MATERIAL_NOT_FOUND_RESPONSE,
)
def get_material_page(
    j_slug: str,
    m_slug: str,
    service: GetMaterialPage = Depends(get_material_page_service),
) -> MaterialPageWire | JSONResponse:
    """Return the SEO material detail page or 404 on slug miss."""
    logger.info("get_material_page: j_slug=%r m_slug=%r", j_slug, m_slug)
    result = service.execute(j_slug, m_slug)
    if result is None:
        return JSONResponse(
            status_code=404,
            content={"error": "not_found"},
        )
    return result
