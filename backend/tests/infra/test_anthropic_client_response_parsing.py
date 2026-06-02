# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false, reportMissingParameterType=false
# Justification: MagicMock's interface is untyped by design; the Any/Unknown
# warnings here originate from unittest.mock.MagicMock and the monkeypatched
# anthropic.Anthropic constructor.
"""Response-parsing robustness for AnthropicClient.

Claude wraps JSON in a ```json ... ``` fence and may append prose after
the closing fence. Both ask() (Sonnet) and classify() (Haiku) must
extract the JSON payload rather than degrading to NoEvaluation / [].
"""

import unittest.mock as mock
import uuid

import anthropic
import pytest

from src.domain.knowledge_base.material import MaterialId
from src.domain.retrieval.evaluated_answer import EvaluatedAnswer, NoEvaluation
from src.domain.retrieval.item_verdict import Accepted
from src.infra.external.anthropic_client import AnthropicClient


def _client_returning(
    text: str, monkeypatch: pytest.MonkeyPatch
) -> AnthropicClient:
    """Build an AnthropicClient whose single SDK response is `text`."""
    messages_spy = mock.MagicMock()
    messages_spy.create.return_value = mock.MagicMock(
        content=[mock.MagicMock(type="text", text=text)]
    )
    fake_sdk = mock.MagicMock()
    fake_sdk.messages = messages_spy
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: fake_sdk)
    return AnthropicClient(api_key="test")


# Verbatim shape observed from Haiku 4.5: a ```json fence followed by a
# prose "Note:" paragraph after the closing fence.
_FENCED_CLASSIFY = (
    "```json\n"
    "[\n"
    '  {"material_id": "11111111-1111-1111-1111-111111111111", '
    '"confidence": 0.85}\n'
    "]\n"
    "```\n\n"
    "**Note:** Without the material definitions I cannot be certain, "
    "but this is my best ranking."
)

_FENCED_ASK = (
    "```json\n"
    '{"verdict": "accepted", '
    '"recommended_action": "Place in your purple curbside cart.", '
    '"confidence": "high", '
    '"citations": [{"title": "Denver Recycles", '
    '"url": "https://denvergov.org/recycling", '
    '"quote": "Aluminum cans are accepted."}]}\n'
    "```"
)


def test_classify_parses_fenced_json_with_trailing_prose(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Haiku fences the array and appends prose; classify still ranks."""
    mid = MaterialId(uuid.UUID("11111111-1111-1111-1111-111111111111"))
    client = _client_returning(_FENCED_CLASSIFY, monkeypatch)

    result = client.classify(
        query_text="aluminum cans", known_material_ids=[mid]
    )

    assert result == [(mid, 0.85)]


def test_ask_parses_fenced_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sonnet fences the answer object; ask parses an EvaluatedAnswer."""
    client = _client_returning(_FENCED_ASK, monkeypatch)

    result = client.ask(
        messages=[{"role": "user", "content": "aluminum cans in denver?"}],
        system_prompt="sys",
    )

    assert isinstance(result, EvaluatedAnswer)
    assert isinstance(result.verdict, Accepted)
    assert len(result.citations) == 1
    assert result.citations[0].url == "https://denvergov.org/recycling"


def test_classify_still_parses_bare_json_array(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare (unfenced) JSON array must keep parsing unchanged."""
    mid = MaterialId(uuid.UUID("22222222-2222-2222-2222-222222222222"))
    bare = (
        '[{"material_id": "22222222-2222-2222-2222-222222222222", '
        '"confidence": 0.5}]'
    )
    client = _client_returning(bare, monkeypatch)

    result = client.classify(query_text="x", known_material_ids=[mid])

    assert result == [(mid, 0.5)]


def test_ask_degrades_to_no_evaluation_on_prose_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prose response with no JSON must degrade, not raise."""
    client = _client_returning("I cannot answer that question.", monkeypatch)

    result = client.ask(
        messages=[{"role": "user", "content": "x"}], system_prompt="sys"
    )

    assert isinstance(result, NoEvaluation)


def test_classify_degrades_to_empty_on_prose_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prose response with no JSON array must degrade classify to []."""
    mid = MaterialId(uuid.UUID("33333333-3333-3333-3333-333333333333"))
    client = _client_returning("Unsure which material you mean.", monkeypatch)

    result = client.classify(query_text="x", known_material_ids=[mid])

    assert result == []


def test_ask_degrades_to_no_evaluation_on_unclosed_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unclosed ```json fence has no regex match; ask must degrade."""
    client = _client_returning('```json\n{"verdict": "accepted"}', monkeypatch)

    result = client.ask(
        messages=[{"role": "user", "content": "x"}], system_prompt="sys"
    )

    assert isinstance(result, NoEvaluation)
