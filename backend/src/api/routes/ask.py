"""POST /ask route -- thin HTTP adapter for the AnswerQuery use case.

Per backend/CLAUDE.md § HTTP API conventions: validates input, calls
exactly one application service via Depends, returns wire response.
No domain imports; no business-logic branches beyond request-shape
validation.

The 500-char cap on `query` is enforced here (HTTP 400 with
error='query_too_long', not HTTP 422) per answer.md § Request.
INV-LLM-004: the cap bounds the prompt-injection surface.
"""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from src.api.deps import get_answer_query
from src.api.schemas.answer import Answer, AskRequest, ErrorEnvelope
from src.application.answer_query import AnswerQuery
from src.application.answer_query_command import AnswerQueryCommand

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_QUERY_LEN = 500


@router.post(
    "/ask",
    response_model=Answer,
    responses={
        400: {
            "model": ErrorEnvelope,
            "description": ("query_too_long -- query exceeds 500 characters"),
        },
    },
)
def ask(
    body: AskRequest,
    service: AnswerQuery = Depends(get_answer_query),
) -> Answer | JSONResponse:
    """Answer a recycling question grounded in jurisdiction rules.

    Returns HTTP 200 for all retrieval outcomes including refusals.
    Returns HTTP 400 with error='query_too_long' when query exceeds
    500 characters.
    """
    if len(body.query) > _MAX_QUERY_LEN:
        logger.warning("ask: query_too_long length=%d", len(body.query))
        return JSONResponse(
            status_code=400,
            content={"error": "query_too_long"},
        )

    command = AnswerQueryCommand(
        query_text=body.query,
        location_input=body.location,
    )
    logger.info(
        "ask: query=%r location=%r",
        body.query[:80],
        body.location,
    )
    return service.execute(command)
