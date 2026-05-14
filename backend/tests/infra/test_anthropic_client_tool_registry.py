"""AnthropicClient tool-registry guard tests.

Verifies that AnthropicClient rejects tool registries containing
destructive operation names at construction time. No network calls
are made; the anthropic.Anthropic constructor is patched.
"""

import unittest.mock as mock

import anthropic
import pytest

from src.infra.external.anthropic_client import AnthropicClient


@pytest.fixture()
def patched_anthropic(monkeypatch: pytest.MonkeyPatch):
    """Patch anthropic.Anthropic so no real SDK calls happen."""
    fake_client = mock.MagicMock()
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: fake_client)
    return fake_client


def test_safe_tool_registry_constructs(patched_anthropic) -> None:
    """AnthropicClient accepts a registry with only safe tool names."""
    client = AnthropicClient(
        api_key="test",
        tool_registry=[
            {"name": "search_rules"},
            {"name": "lookup_jurisdiction"},
        ],
    )
    assert isinstance(client, AnthropicClient)


@pytest.mark.parametrize(
    "bad_name",
    [
        "write_rule",
        "update_rule",
        "delete_rule",
        "drop_table",
        "exec_sql",
        "insert_row",
        # Case-insensitivity arms: the regex is compiled with re.IGNORECASE;
        # pin that branch so a future refactor cannot drop the flag silently.
        "WRITE_RULE",
        "Delete_Rule",
    ],
)
def test_destructive_tool_name_raises_value_error(
    patched_anthropic, bad_name: str
) -> None:
    """AnthropicClient raises ValueError for any destructive tool name."""
    with pytest.raises(ValueError, match=bad_name):
        AnthropicClient(
            api_key="test",
            tool_registry=[{"name": bad_name}],
        )
