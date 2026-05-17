"""FastAPI route tests for POST /ask and page routes.

Tests use Starlette TestClient with FastAPI dependency overrides to
inject fake application services -- no Postgres, no Anthropic SDK.

Behavior checks per Phase 6 plan:
  - happy-path response shape (Denver)
  - HTTP 400 on 501-char query (INV-LLM-004 length cap)
  - out-of-jurisdiction (Aurora) returns short_answer='unknown',
    citations=[], non-empty audit_record_id, no Anthropic call
  - 404 on slug-miss for both page routes
"""

import uuid
from typing import final

from fastapi.testclient import TestClient

from src.api.deps import (
    get_answer_query,
    get_jurisdiction_page_service,
    get_material_page_service,
)
from src.api.schemas.answer import (
    Answer,
    CitationWire,
    JurisdictionRefWire,
)
from src.api.schemas.jurisdiction_page import (
    JurisdictionPageWire,
    JurisdictionWire,
    MaterialDetailWire,
    MaterialPageWire,
    MaterialSummaryWire,
    RuleWire,
)
from src.application.answer_query_command import AnswerQueryCommand
from src.main import app

# ---------------------------------------------------------------------------
# Fake application services (port doubles)
# ---------------------------------------------------------------------------


@final
class _FakeAnswerQuery:
    """Returns a pre-canned Answer; records call count."""

    def __init__(self, result: Answer) -> None:
        self._result = result
        self.call_count = 0

    def execute(self, command: AnswerQueryCommand) -> Answer:
        self.call_count += 1
        return self._result


@final
class _FakeGetJurisdictionPage:
    """Returns a pre-canned JurisdictionPageWire or None."""

    def __init__(self, result: JurisdictionPageWire | None) -> None:
        self._result = result
        self.call_count = 0

    def execute(self, slug: str) -> JurisdictionPageWire | None:
        self.call_count += 1
        return self._result


@final
class _FakeGetMaterialPage:
    """Returns a pre-canned MaterialPageWire or None."""

    def __init__(self, result: MaterialPageWire | None) -> None:
        self._result = result
        self.call_count = 0

    def execute(
        self, jurisdiction_slug: str, material_slug: str
    ) -> MaterialPageWire | None:
        self.call_count += 1
        return self._result


# ---------------------------------------------------------------------------
# Wire fixtures
# ---------------------------------------------------------------------------

_DENVER_AUDIT_ID = str(uuid.uuid4())
_AURORA_AUDIT_ID = str(uuid.uuid4())


def _denver_answer() -> Answer:
    return Answer(
        audit_record_id=_DENVER_AUDIT_ID,
        citations=[
            CitationWire(
                title="Denver Recycling Guide",
                url="https://denvergov.org/recycling",
                quote="Aluminum cans are accepted curbside.",
            )
        ],
        clarifying_question=None,
        confidence="high",
        do_not_do=[],
        dropoff_options=[],
        jurisdiction=JurisdictionRefWire(id=str(uuid.uuid4()), name="Denver"),
        preparation_steps=[],
        recommended_action="Rinse and recycle aluminum cans curbside.",
        refusal_reason=None,
        short_answer="yes",
    )


def _aurora_answer() -> Answer:
    return Answer(
        audit_record_id=_AURORA_AUDIT_ID,
        citations=[],
        clarifying_question=None,
        confidence="low",
        do_not_do=[],
        dropoff_options=[],
        jurisdiction=JurisdictionRefWire(id=None, name="Aurora"),
        preparation_steps=[],
        recommended_action=(
            "Aurora is not yet covered. Check local guidelines."
        ),
        refusal_reason="out_of_jurisdiction",
        short_answer="unknown",
    )


def _jurisdiction_page() -> JurisdictionPageWire:
    return JurisdictionPageWire(
        jurisdiction=JurisdictionWire(
            id=str(uuid.uuid4()),
            name="Denver",
            slug="denver-co-us",
        ),
        materials=[
            MaterialSummaryWire(
                id=str(uuid.uuid4()),
                slug="aluminum-cans",
                canonical_name="Aluminum Cans",
                accepted_status="accepted",
                needs_preparation=False,
                citation=CitationWire(
                    title="Denver Recycling Guide",
                    url="https://denvergov.org/recycling",
                    quote=None,
                ),
            )
        ],
    )


def _material_page() -> MaterialPageWire:
    return MaterialPageWire(
        jurisdiction=JurisdictionWire(
            id=str(uuid.uuid4()),
            name="Denver",
            slug="denver-co-us",
        ),
        material=MaterialDetailWire(
            id=str(uuid.uuid4()),
            slug="aluminum-cans",
            canonical_name="Aluminum Cans",
        ),
        rule=RuleWire(
            disposition="curbside_recycle",
            accepted_status="accepted",
            preparation_steps=[],
            exceptions=[],
            warnings=[],
        ),
        citations=[
            CitationWire(
                title="Denver Recycling Guide",
                url="https://denvergov.org/recycling",
                quote=None,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Helper: TestClient without lifespan (avoids boot-check env requirements)
# ---------------------------------------------------------------------------


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# POST /ask -- happy path (Denver)
# ---------------------------------------------------------------------------


def test_ask_denver_happy_path_response_shape() -> None:
    """POST /ask with a Denver location returns a valid Answer shape."""
    fake_svc = _FakeAnswerQuery(_denver_answer())

    def _override() -> _FakeAnswerQuery:
        return fake_svc

    app.dependency_overrides[get_answer_query] = _override
    try:
        resp = _client().post(
            "/ask",
            json={
                "query": "Can I recycle aluminum cans in Denver?",
                "location": "Denver",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["short_answer"] in {"yes", "no", "conditional", "unknown"}
        assert isinstance(body["citations"], list)
        assert isinstance(body["audit_record_id"], str)
        assert len(body["audit_record_id"]) > 0
        assert body["audit_record_id"] == _DENVER_AUDIT_ID
        assert body["short_answer"] == "yes"
        assert len(body["citations"]) > 0
    finally:
        app.dependency_overrides.pop(get_answer_query, None)


# ---------------------------------------------------------------------------
# POST /ask -- 400 on 501-character query (INV-LLM-004)
# ---------------------------------------------------------------------------


def test_ask_501_char_query_returns_400() -> None:
    """POST /ask with query > 500 chars returns HTTP 400 error='query_too_long'.

    Validates INV-LLM-004: the 500-char cap bounds the prompt-injection
    surface. The route enforces this before delegating to the application
    service.
    """
    long_query = "x" * 501

    resp = _client().post(
        "/ask",
        json={"query": long_query, "location": "Denver"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "query_too_long"


# ---------------------------------------------------------------------------
# POST /ask -- out-of-jurisdiction (Aurora)
# ---------------------------------------------------------------------------


def test_ask_aurora_ooj_shape_and_no_llm_call() -> None:
    """POST /ask with location='Aurora' returns unknown/OOJ shape.

    The fake service returns the Aurora answer without ever touching
    an LLM; the test verifies:
      - short_answer == 'unknown'
      - citations == []
      - audit_record_id is a non-empty string
      - the application service was called exactly once
    """
    fake_svc = _FakeAnswerQuery(_aurora_answer())

    def _override() -> _FakeAnswerQuery:
        return fake_svc

    app.dependency_overrides[get_answer_query] = _override
    try:
        resp = _client().post(
            "/ask",
            json={
                "query": "Can I recycle aluminum cans?",
                "location": "Aurora",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["short_answer"] == "unknown"
        assert body["citations"] == []
        assert isinstance(body["audit_record_id"], str)
        assert len(body["audit_record_id"]) > 0
        # Assert fake service was used (no real Anthropic call possible).
        assert fake_svc.call_count == 1
    finally:
        app.dependency_overrides.pop(get_answer_query, None)


# ---------------------------------------------------------------------------
# GET /pages/jurisdiction/{slug} -- happy path
# ---------------------------------------------------------------------------


def test_jurisdiction_page_happy_path() -> None:
    """GET /pages/jurisdiction/denver-co-us returns a JurisdictionPageWire."""
    fake_svc = _FakeGetJurisdictionPage(_jurisdiction_page())

    def _override() -> _FakeGetJurisdictionPage:
        return fake_svc

    app.dependency_overrides[get_jurisdiction_page_service] = _override
    try:
        resp = _client().get("/pages/jurisdiction/denver-co-us")
        assert resp.status_code == 200
        body = resp.json()
        assert body["jurisdiction"]["slug"] == "denver-co-us"
        assert isinstance(body["materials"], list)
    finally:
        app.dependency_overrides.pop(get_jurisdiction_page_service, None)


# ---------------------------------------------------------------------------
# GET /pages/jurisdiction/{slug} -- 404 on slug miss
# ---------------------------------------------------------------------------


def test_jurisdiction_page_slug_miss_returns_404() -> None:
    """GET /pages/jurisdiction/{unknown} returns HTTP 404 error='not_found'."""
    fake_svc = _FakeGetJurisdictionPage(None)

    def _override() -> _FakeGetJurisdictionPage:
        return fake_svc

    app.dependency_overrides[get_jurisdiction_page_service] = _override
    try:
        resp = _client().get("/pages/jurisdiction/does-not-exist")
        assert resp.status_code == 404
        assert resp.json()["error"] == "not_found"
    finally:
        app.dependency_overrides.pop(get_jurisdiction_page_service, None)


# ---------------------------------------------------------------------------
# GET /pages/jurisdiction/{slug}/material/{slug} -- happy path
# ---------------------------------------------------------------------------


def test_material_page_happy_path() -> None:
    """GET /pages/jurisdiction/{j}/material/{m} returns MaterialPageWire."""
    fake_svc = _FakeGetMaterialPage(_material_page())

    def _override() -> _FakeGetMaterialPage:
        return fake_svc

    app.dependency_overrides[get_material_page_service] = _override
    try:
        resp = _client().get(
            "/pages/jurisdiction/denver-co-us/material/aluminum-cans"
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["jurisdiction"]["slug"] == "denver-co-us"
        assert body["material"]["slug"] == "aluminum-cans"
        assert "rule" in body
    finally:
        app.dependency_overrides.pop(get_material_page_service, None)


# ---------------------------------------------------------------------------
# GET /pages/jurisdiction/{slug}/material/{slug} -- 404 on slug miss
# ---------------------------------------------------------------------------


def test_material_page_slug_miss_returns_404() -> None:
    """GET /pages/jurisdiction/{j}/material/{unknown} returns 404."""
    fake_svc = _FakeGetMaterialPage(None)

    def _override() -> _FakeGetMaterialPage:
        return fake_svc

    app.dependency_overrides[get_material_page_service] = _override
    try:
        resp = _client().get(
            "/pages/jurisdiction/denver-co-us/material/not-a-material"
        )
        assert resp.status_code == 404
        assert resp.json()["error"] == "not_found"
    finally:
        app.dependency_overrides.pop(get_material_page_service, None)
