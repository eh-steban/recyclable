# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false, reportMissingParameterType=false
# pyright: reportUnknownParameterType=false
# Justification: MagicMock's interface is untyped by design; the Any/Unknown
# warnings here originate from unittest.mock.MagicMock and the monkeypatched
# anthropic.Anthropic constructor.
"""classify() prompt-construction tests.

The Haiku classify path delimits BOTH the user query and the material
catalog with XML-style tags. The catalog is system-supplied data, not
user instructions, so a crafted query must not be able to forge catalog
entries by breaking out of the query delimiter (INV-LLM-004).
"""

import unittest.mock as mock
import uuid

import anthropic
import pytest

from src.domain.knowledge_base.material import (
    Material,
    MaterialCategory,
    MaterialId,
)
from src.infra.external.anthropic_client import AnthropicClient


def _client_with_spy(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[AnthropicClient, mock.MagicMock]:
    """Build an AnthropicClient whose SDK calls are captured by a spy."""
    messages_spy = mock.MagicMock()
    messages_spy.create.return_value = mock.MagicMock(
        content=[mock.MagicMock(type="text", text="[]")]
    )
    fake_sdk = mock.MagicMock()
    fake_sdk.messages = messages_spy
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: fake_sdk)
    return AnthropicClient(api_key="test"), messages_spy


def _mat(name: str) -> Material:
    return Material(
        id=MaterialId(uuid.uuid4()),
        canonical_name=name,
        slug=name.lower().replace(" ", "-"),
        category=MaterialCategory.METAL,
    )


def _user_message(spy: mock.MagicMock) -> str:
    call_kwargs = spy.create.call_args
    assert call_kwargs is not None, "messages.create was not called"
    return call_kwargs.kwargs["messages"][0]["content"]


def test_classify_delimits_user_query_and_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The query and the catalog are each wrapped in their own tags."""
    client, spy = _client_with_spy(monkeypatch)

    client.classify(
        query_text="aluminum cans",
        known_materials=[_mat("Aluminum can")],
    )

    user_msg = _user_message(spy)
    assert "<user_query>aluminum cans</user_query>" in user_msg
    assert "<catalog>" in user_msg
    assert "</catalog>" in user_msg
