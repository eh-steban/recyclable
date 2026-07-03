# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false, reportMissingParameterType=false
# Justification: MagicMock's interface is untyped by design; the Any/Unknown
# warnings originate from unittest.mock.MagicMock and the monkeypatched
# anthropic.Anthropic constructor.
"""Guard for INV-LLM-008: extraction system prompt uses display name, not UUID.

The system prompt passed to Opus for extraction must contain the jurisdiction
display name (e.g. "Denver, CO") and must not contain the jurisdiction UUID.
"""

import unittest.mock as mock
import uuid

import anthropic
import pytest

from src.domain.ingestion.source_fetcher import SourceFetchResult
from src.infra.external.anthropic_client import OpusIngestionClient

_JURISDICTION_ID = str(uuid.uuid4())
_JURISDICTION_NAME = "Denver, CO"


def _opus_client_with_spy(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[OpusIngestionClient, mock.MagicMock]:
    """Build an OpusIngestionClient whose SDK messages.create is a spy."""
    messages_spy = mock.MagicMock()
    messages_spy.create.return_value = mock.MagicMock(
        content=[],
        stop_reason="end_turn",
    )
    fake_sdk = mock.MagicMock(spec=anthropic.Anthropic)
    fake_sdk.messages = messages_spy
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: fake_sdk)
    client = OpusIngestionClient(api_key="test")
    return client, messages_spy


def _minimal_source() -> SourceFetchResult:
    return SourceFetchResult(
        id=uuid.uuid4(),
        url="https://denvergov.org/recycling",
        source_text="Glass bottles are accepted curbside.",
        source_text_hash="abc123",
        authority_level=3,
        content_type="text/html",
    )


class TestExtractionPromptJurisdictionName:
    def test_system_prompt_contains_display_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """INV-LLM-008: system prompt must contain the display name."""
        client, spy = _opus_client_with_spy(monkeypatch)
        client.extract(
            source=_minimal_source(),
            jurisdiction_id=_JURISDICTION_ID,
            jurisdiction_name=_JURISDICTION_NAME,
            prompt_name="extract_rules_v1",
            prompt_version=1,
        )
        call_kwargs = spy.create.call_args
        system_blocks = call_kwargs.kwargs["system"]
        system_text = " ".join(
            b["text"] for b in system_blocks if b.get("type") == "text"
        )
        assert _JURISDICTION_NAME in system_text

    def test_system_prompt_does_not_contain_raw_uuid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """INV-LLM-008: system prompt must not embed the jurisdiction UUID."""
        client, spy = _opus_client_with_spy(monkeypatch)
        client.extract(
            source=_minimal_source(),
            jurisdiction_id=_JURISDICTION_ID,
            jurisdiction_name=_JURISDICTION_NAME,
            prompt_name="extract_rules_v1",
            prompt_version=1,
        )
        call_kwargs = spy.create.call_args
        system_blocks = call_kwargs.kwargs["system"]
        system_text = " ".join(
            b["text"] for b in system_blocks if b.get("type") == "text"
        )
        assert _JURISDICTION_ID not in system_text

    def test_url_with_special_chars_is_xml_escaped_in_user_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """URL containing XML-special chars must be escaped in the user message.

        An unescaped URL with '"', '>' or '&' breaks the XML attribute
        structure of the <source_document> tag and can cause Opus to
        misparse the document boundary.
        """
        client, spy = _opus_client_with_spy(monkeypatch)
        source = SourceFetchResult(
            id=uuid.uuid4(),
            url='https://example.com/page?a=1&b=2&c="test">',
            source_text="Glass is accepted.",
            source_text_hash="abc",
            authority_level=3,
            content_type="text/html",
        )
        client.extract(
            source=source,
            jurisdiction_id=_JURISDICTION_ID,
            jurisdiction_name=_JURISDICTION_NAME,
            prompt_name="extract_rules_v1",
            prompt_version=1,
        )
        call_kwargs = spy.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_content: str = messages[0]["content"]
        # Raw '&' and '"' must not appear unescaped inside the url attribute.
        # (The closing '>' ends the XML tag, not the URL value.)
        assert 'url="https://example.com/page?a=1&b=' not in user_content
        assert 'c="test">' not in user_content
        # The escaped forms must be present in the user message.
        assert "&amp;" in user_content
        assert "&quot;" in user_content
        assert "&gt;" in user_content
