"""Wire schemas for POST /ask -- AskRequest and Answer.

Shapes per private/specs/contracts/answer.md.
These are Pydantic v2 models; they live in api/schemas/ and are
never imported by the domain layer.
"""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Shared error envelope (answer.md § Error shapes)
# ---------------------------------------------------------------------------


class ErrorEnvelope(BaseModel):
    """Typed error envelope for application-level errors.

    All non-2xx application errors use this shape:
      { "error": "<machine_code>" }

    Known codes per answer.md § Known error codes:
      query_too_long  -- 400, POST /ask, query > 500 chars
      not_found       -- 404, page routes, slug miss
      internal_error  -- 500, all routes, unhandled server error
    """

    error: str


# ---------------------------------------------------------------------------
# Nested types
# ---------------------------------------------------------------------------


class CitationWire(BaseModel):
    """A source citation in the wire response.

    quote is optional -- omitted when no source quote is available.
    Per answer.md § Citation.
    """

    title: str
    url: str
    quote: str | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)


class FacilityWire(BaseModel):
    """A dropoff facility.

    Always [] in Step 2. Shape defined so consumers can type the
    field ahead of Step 3.
    """

    id: str
    name: str
    address: str


class JurisdictionRefWire(BaseModel):
    """A resolved jurisdiction reference. id is always a non-empty UUID."""

    id: str | None
    name: str


# ---------------------------------------------------------------------------
# AskRequest
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    """POST /ask request body per answer.md § Request."""

    query: str = Field(
        ...,
        description="Free-text user question, max 500 chars",
    )
    location: str = Field(
        ...,
        description="City name, 'Denver, CO', or ZIP",
    )


# ---------------------------------------------------------------------------
# Answer
# ---------------------------------------------------------------------------


class Answer(BaseModel):
    """POST /ask response body per answer.md § Response.

    HTTP 200 for all retrieval outcomes including refusals.
    """

    audit_record_id: str
    citations: list[CitationWire]
    clarifying_question: str | None
    confidence: str  # 'high' | 'medium' | 'low'
    do_not_do: list[str]
    dropoff_options: list[FacilityWire]
    jurisdiction: JurisdictionRefWire
    preparation_steps: list[str]
    recommended_action: str
    refusal_reason: str | None  # see answer.md § Response
    short_answer: str  # 'yes' | 'no' | 'conditional' | 'unknown'
