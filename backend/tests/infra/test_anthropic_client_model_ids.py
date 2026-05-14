"""AnthropicClient model-id pin tests (INV-LLM-005).

Asserts that ask() dispatches to the Sonnet model and classify()
dispatches to the Haiku model. No network calls; the SDK is patched.
"""

import unittest.mock as mock

import anthropic
import pytest

from src.domain.retrieval.evaluated_answer import (
    NoEvaluation,
    NoEvaluationReason,
)
from src.infra.external.anthropic_client import (
    HAIKU_MODEL_ID,
    SONNET_MODEL_ID,
    AnthropicClient,
)


@pytest.fixture()
def client_with_spy(monkeypatch: pytest.MonkeyPatch):
    """Return an AnthropicClient whose underlying SDK calls are captured."""
    # Build a spy that records calls to messages.create.
    messages_spy = mock.MagicMock()
    # ask() path: return a well-formed but minimal response so parsing
    # degrades gracefully to NoEvaluation rather than raising.
    messages_spy.create.return_value = mock.MagicMock(
        content=[mock.MagicMock(type="text", text="{}")]
    )

    fake_sdk = mock.MagicMock()
    fake_sdk.messages = messages_spy

    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: fake_sdk)

    return AnthropicClient(api_key="test"), messages_spy


def test_ask_uses_sonnet_model(client_with_spy) -> None:
    """ask() must call the Anthropic SDK with model=SONNET_MODEL_ID."""
    client, spy = client_with_spy
    client.ask(
        messages=[{"role": "user", "content": "is cardboard recyclable?"}],
        system_prompt="You are a recycling assistant.",
    )

    call_kwargs = spy.create.call_args
    assert call_kwargs is not None, "messages.create was not called"
    model_used = call_kwargs.kwargs.get(
        "model", call_kwargs.args[0] if call_kwargs.args else None
    )
    assert model_used == SONNET_MODEL_ID, (
        f"Expected {SONNET_MODEL_ID!r}, got {model_used!r}"
    )


def test_classify_uses_haiku_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """classify() must call the Anthropic SDK with model=HAIKU_MODEL_ID."""
    messages_spy = mock.MagicMock()
    messages_spy.create.return_value = mock.MagicMock(
        content=[mock.MagicMock(type="text", text="[]")]
    )

    fake_sdk = mock.MagicMock()
    fake_sdk.messages = messages_spy

    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: fake_sdk)

    client = AnthropicClient(api_key="test")
    client.classify(query_text="cardboard box", known_material_ids=[])

    call_kwargs = messages_spy.create.call_args
    assert call_kwargs is not None, "messages.create was not called"
    model_used = call_kwargs.kwargs.get(
        "model", call_kwargs.args[0] if call_kwargs.args else None
    )
    assert model_used == HAIKU_MODEL_ID, (
        f"Expected {HAIKU_MODEL_ID!r}, got {model_used!r}"
    )


def test_ask_returns_llm_rejected_on_api_status_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ask() must return NoEvaluation(LLM_REJECTED) on Anthropic 5xx.

    INV-PROD-004: LLM unavailability is LLM_REJECTED, never
    VALIDATOR_REJECTED. The model did not produce output, so there
    was no validator decision to record.
    """
    messages_spy = mock.MagicMock()
    err = anthropic.APIStatusError(
        message="upstream 503",
        response=mock.MagicMock(status_code=503),
        body=None,
    )
    messages_spy.create.side_effect = err

    fake_sdk = mock.MagicMock()
    fake_sdk.messages = messages_spy
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: fake_sdk)

    client = AnthropicClient(api_key="test")
    result = client.ask(
        messages=[{"role": "user", "content": "hi"}],
        system_prompt="sys",
    )

    assert isinstance(result, NoEvaluation)
    assert result.reason == NoEvaluationReason.LLM_REJECTED


def test_ask_returns_llm_rejected_on_generic_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ask() must return NoEvaluation(LLM_REJECTED) on any non-status error.

    The generic `except Exception` branch is the catch-all for network
    failures, SDK bugs, and unexpected runtime errors. INV-PROD-004
    requires LLM_REJECTED here too -- the model produced no output.
    """
    messages_spy = mock.MagicMock()
    messages_spy.create.side_effect = ConnectionError("network down")

    fake_sdk = mock.MagicMock()
    fake_sdk.messages = messages_spy
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: fake_sdk)

    client = AnthropicClient(api_key="test")
    result = client.ask(
        messages=[{"role": "user", "content": "hi"}],
        system_prompt="sys",
    )

    assert isinstance(result, NoEvaluation)
    assert result.reason == NoEvaluationReason.LLM_REJECTED


def test_ask_retries_once_on_429_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_call_with_retry must retry exactly once on 429 and then succeed.

    Pins the retry policy: a single retry on retryable status codes
    (429 / 5xx), after which a successful response parses normally.
    """
    success = mock.MagicMock(content=[mock.MagicMock(type="text", text="{}")])
    err_429 = anthropic.APIStatusError(
        message="rate limited",
        response=mock.MagicMock(status_code=429),
        body=None,
    )
    messages_spy = mock.MagicMock()
    messages_spy.create.side_effect = [err_429, success]

    fake_sdk = mock.MagicMock()
    fake_sdk.messages = messages_spy
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: fake_sdk)

    client = AnthropicClient(api_key="test")
    client.ask(
        messages=[{"role": "user", "content": "hi"}],
        system_prompt="sys",
    )

    assert messages_spy.create.call_count == 2, (
        "Expected one retry on 429 (total 2 calls); "
        f"got {messages_spy.create.call_count}"
    )


def test_ask_does_not_retry_on_non_retryable_4xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-retryable 4xx (400, 401, 403, 404) must not trigger a retry.

    Only 429 and 5xx are retryable per the adapter's policy. A 400
    propagates immediately as LLM_REJECTED with exactly one call.
    """
    err_400 = anthropic.APIStatusError(
        message="bad request",
        response=mock.MagicMock(status_code=400),
        body=None,
    )
    messages_spy = mock.MagicMock()
    messages_spy.create.side_effect = err_400

    fake_sdk = mock.MagicMock()
    fake_sdk.messages = messages_spy
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: fake_sdk)

    client = AnthropicClient(api_key="test")
    result = client.ask(
        messages=[{"role": "user", "content": "hi"}],
        system_prompt="sys",
    )

    assert messages_spy.create.call_count == 1, (
        f"Expected no retry on 400; got {messages_spy.create.call_count} calls"
    )
    assert isinstance(result, NoEvaluation)
    assert result.reason == NoEvaluationReason.LLM_REJECTED
