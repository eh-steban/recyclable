"""Offline /ask pipeline tests with a fake LLM.

These run by default -- no key, no network, no cost. They inject a fake
RetrievalLLM/normalizer so the full HTTP path (retrieval, grounding,
audit write, wire mapping) runs deterministically.

The assertions are on what the *pipeline* does with a given model answer,
not on the canned answer itself. The clearest proof of that is the
accept/refuse contrast: a grounded "accepted" becomes a cited "yes", but
the *same* "accepted" citing an unretrieved URL is refused by the
grounding check (INV-LLM-002), and an out-of-jurisdiction query is refused
before the model is ever consulted.
"""

import re
import uuid
from collections.abc import Callable, Generator

import httpx
import pytest
from sqlalchemy.orm import Session

from src.api.deps import get_anthropic_client
from src.domain.knowledge_base.material import Material, MaterialId
from src.domain.retrieval.citation import Citation
from src.domain.retrieval.evaluated_answer import (
    EvaluatedAnswer,
    NoEvaluation,
    NoEvaluationReason,
)
from src.domain.retrieval.item_verdict import Accepted
from src.domain.retrieval.retrieval_llm import LLMMessage
from src.infra.db.models.answer_audit_record import AnswerAuditRecordORM
from src.main import app
from tests.utils.fakes.anthropic_client import FakeAnthropicClient

_DENVER_QUERY = "Can I recycle aluminum cans in Denver?"


@pytest.fixture()
def install_fake_llm() -> Generator[Callable[[FakeAnthropicClient], None]]:
    """Yield a setter that installs a fake as the app's Anthropic client."""

    def _install(fake: FakeAnthropicClient) -> None:
        app.dependency_overrides[get_anthropic_client] = lambda: fake

    yield _install
    app.dependency_overrides.pop(get_anthropic_client, None)


def _resolve_by_name(
    needle: str,
) -> Callable[[str, list[Material]], list[tuple[MaterialId, float]]]:
    """Fake classify that resolves the catalog material matching *needle*.

    Reads the candidate from the catalog the pipeline supplies, so the
    material resolves whether or not trigram search hits first -- no
    hard-coded ids.
    """

    def _classify(
        _query: str, known_materials: list[Material]
    ) -> list[tuple[MaterialId, float]]:
        for material in known_materials:
            if needle in material.canonical_name.lower():
                return [(material.id, 0.99)]
        return []

    return _classify


def _audit_row(session: Session, audit_record_id: str) -> AnswerAuditRecordORM:
    row = session.get(AnswerAuditRecordORM, uuid.UUID(audit_record_id))
    assert row is not None, f"no audit row for {audit_record_id}"
    return row


async def test_grounded_accept_returns_cited_yes(
    asgi_client: httpx.AsyncClient,
    regression_db_session: Session,
    install_fake_llm: Callable[[FakeAnthropicClient], None],
) -> None:
    """An accepted verdict citing a retrieved source becomes a cited 'yes'."""

    grounded_url: dict[str, str] = {}

    def _ask(
        _messages: list[LLMMessage], system_prompt: str
    ) -> EvaluatedAnswer:
        # Cite a URL drawn from the retrieved rule context, so the citation
        # is in the retrieved-source set by construction.
        match = re.search(r"https?://[^\s\"'<>)\]]+", system_prompt)
        assert match is not None, "expected a source URL in the prompt"
        grounded_url["value"] = match.group(0)
        return EvaluatedAnswer(
            verdict=Accepted(),
            citations=(Citation(title="Denver Recycling", url=match.group(0)),),
            recommended_action="Place empty cans in your recycling cart.",
            confidence="high",
            retrieved_source_urls=frozenset(),
        )

    fake = FakeAnthropicClient(
        ask_result=_ask, classify_result=_resolve_by_name("aluminum")
    )
    install_fake_llm(fake)

    response = await asgi_client.post(
        "/ask",
        json={"query": _DENVER_QUERY, "location": "denver"},
        timeout=10.0,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["short_answer"] == "yes", body
    # The grounded citation must survive to the wire unchanged -- the
    # pipeline surfaces the source the model cited, it does not drop or
    # rewrite it.
    wire_urls = [c["url"] for c in body["citations"]]
    assert grounded_url["value"] in wire_urls, (
        f"grounded URL {grounded_url['value']!r} missing from {wire_urls}"
    )

    row = _audit_row(regression_db_session, body["audit_record_id"])
    assert row.verdict == "yes"
    assert row.outcome_kind == "evaluated"
    assert fake.ask_calls, "the LLM seam should have been exercised"


async def test_ungrounded_accept_is_refused(
    asgi_client: httpx.AsyncClient,
    regression_db_session: Session,
    install_fake_llm: Callable[[FakeAnthropicClient], None],
) -> None:
    """The same accept citing an unretrieved URL is refused by grounding."""
    fake = FakeAnthropicClient(
        ask_result=EvaluatedAnswer(
            verdict=Accepted(),
            citations=(
                Citation(
                    title="Fabricated",
                    url="https://not-a-retrieved-source.example/made-up",
                ),
            ),
            recommended_action="Recycle it.",
            confidence="high",
            retrieved_source_urls=frozenset(),
        ),
        classify_result=_resolve_by_name("aluminum"),
    )
    install_fake_llm(fake)

    response = await asgi_client.post(
        "/ask",
        json={"query": _DENVER_QUERY, "location": "denver"},
        timeout=10.0,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    # The model said "accepted"; the system refuses it because the cited
    # URL is not in the retrieved source set (INV-LLM-002).
    assert body["short_answer"] == "unknown", body
    assert body["citations"] == [], "an ungrounded answer must not cite"

    row = _audit_row(regression_db_session, body["audit_record_id"])
    assert row.outcome_kind == "no_evaluation"
    assert row.no_evaluation_reason == "validator_rejected"
    assert fake.ask_calls, "the LLM seam should have been exercised"


async def test_llm_rejection_is_refused(
    asgi_client: httpx.AsyncClient,
    regression_db_session: Session,
    install_fake_llm: Callable[[FakeAnthropicClient], None],
) -> None:
    """LLM failure maps to a refusal, reason llm_rejected (INV-PROD-004)."""
    fake = FakeAnthropicClient(
        ask_result=NoEvaluation(reason=NoEvaluationReason.LLM_REJECTED),
        classify_result=_resolve_by_name("aluminum"),
    )
    install_fake_llm(fake)

    response = await asgi_client.post(
        "/ask",
        json={"query": _DENVER_QUERY, "location": "denver"},
        timeout=10.0,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["short_answer"] == "unknown", body
    assert body["citations"] == []

    row = _audit_row(regression_db_session, body["audit_record_id"])
    assert row.outcome_kind == "no_evaluation"
    assert row.no_evaluation_reason == "llm_rejected"


async def test_out_of_jurisdiction_never_calls_the_llm(
    asgi_client: httpx.AsyncClient,
    regression_db_session: Session,
    install_fake_llm: Callable[[FakeAnthropicClient], None],
) -> None:
    """An out-of-jurisdiction query is refused before the LLM is consulted."""
    fake = FakeAnthropicClient(
        ask_result=EvaluatedAnswer(
            verdict=Accepted(),
            citations=(Citation(title="x", url="https://example.com/x"),),
            recommended_action="should never be returned",
            confidence="high",
            retrieved_source_urls=frozenset(),
        ),
        classify_result=_resolve_by_name("aluminum"),
    )
    install_fake_llm(fake)

    response = await asgi_client.post(
        "/ask",
        json={
            "query": "Can I recycle aluminum cans in Aurora?",
            "location": "Aurora",
        },
        timeout=10.0,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["short_answer"] == "unknown", body
    assert body["citations"] == []

    row = _audit_row(regression_db_session, body["audit_record_id"])
    assert row.no_evaluation_reason == "out_of_jurisdiction"
    # The jurisdiction refusal must short-circuit before any model call.
    assert fake.ask_calls == [], "OOJ must not spend an LLM call"
