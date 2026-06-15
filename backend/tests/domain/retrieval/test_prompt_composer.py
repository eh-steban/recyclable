"""Tests for ask_compose_v1 prompt composition.

Pins the three pieces the Sonnet user path depends on: the user turn
delimits the query (INV-LLM-004), the system prompt carries the
grounding contract + answer JSON schema, and the retrieved rule + source
block is rendered with the exact source URL the model must cite back
(INV-LLM-002).
"""

import uuid

from src.domain.knowledge_base.rule import AcceptedStatus, Disposition
from src.domain.knowledge_base.source import SourceId
from src.domain.retrieval.prompt_composer import (
    ask_compose_v1,
    format_rule_context,
)
from src.domain.retrieval.query import Query
from tests.utils.builders import make_rule, make_source_document


class TestUserTurn:
    """The user message delimits the query (INV-LLM-004)."""

    def test_query_wrapped_in_delimiters(self) -> None:
        query = Query(
            text="Can I recycle aluminum cans?", location_input="Denver"
        )
        prompt = ask_compose_v1(query, rule_context="RETRIEVED RULES:\n(none)")

        assert len(prompt.messages) == 1
        content = prompt.messages[0]["content"]
        assert (
            "<user_query>Can I recycle aluminum cans?</user_query>" in content
        )
        assert "Denver" in content

    def test_rule_context_not_leaked_into_user_turn(self) -> None:
        """Retrieved rules live in the system prompt, never the user turn."""
        query = Query(text="aluminum cans", location_input="Denver")
        rule_context = "RETRIEVED RULES:\n  source_url: https://secret.example"

        prompt = ask_compose_v1(query, rule_context=rule_context)

        assert "https://secret.example" not in prompt.messages[0]["content"]


class TestSystemPrompt:
    """The system prompt carries the grounding contract, the answer JSON
    schema, and the retrieved rule + source block.
    """

    def test_contains_answer_schema_keys(self) -> None:
        query = Query(text="aluminum cans", location_input="Denver")
        prompt = ask_compose_v1(query, rule_context="RETRIEVED RULES:\n(none)")

        for key in ("verdict", "recommended_action", "citations", "confidence"):
            assert key in prompt.system_prompt, f"schema key {key!r} missing"

    def test_contains_grounding_contract(self) -> None:
        query = Query(text="aluminum cans", location_input="Denver")
        prompt = ask_compose_v1(query, rule_context="RETRIEVED RULES:\n(none)")

        lowered = prompt.system_prompt.lower()
        # Refusal verdict and the cite-or-refuse rule must be stated.
        assert "not_covered" in lowered
        assert "citation" in lowered or "cite" in lowered

    def test_embeds_rule_context_block(self) -> None:
        query = Query(text="aluminum cans", location_input="Denver")
        rule_context = "RETRIEVED RULES:\n  marker-12345"

        prompt = ask_compose_v1(query, rule_context=rule_context)

        assert "marker-12345" in prompt.system_prompt


class TestFormatRuleContext:
    """format_rule_context renders rules with their citable source data."""

    def test_includes_status_disposition_quote_and_source(self) -> None:
        source_id = SourceId(uuid.uuid4())
        url = "https://denvergov.org/recycling/accepted"
        rule = make_rule(
            source_document_id=source_id,
            disposition=Disposition.CURBSIDE_RECYCLE,
            accepted_status=AcceptedStatus.ACCEPTED,
            source_quote="Aluminum beverage cans are accepted curbside.",
        )
        source = make_source_document(
            id=source_id, url=url, title="Denver Accepted-for-Recycling"
        )

        block = format_rule_context([rule], {source_id: source})

        assert "accepted" in block
        assert "curbside_recycle" in block
        assert "Aluminum beverage cans are accepted curbside." in block
        assert url in block
        assert "Denver Accepted-for-Recycling" in block

    def test_missing_source_is_marked_uncitable(self) -> None:
        """A rule whose source is absent contributes no URL and is flagged
        so the model does not fabricate a citation (INV-LLM-002).
        """
        source_id = SourceId(uuid.uuid4())
        rule = make_rule(source_document_id=source_id)

        block = format_rule_context([rule], {})

        assert "source_url" not in block  # no citable URL emitted
        assert "http" not in block
        assert "unavailable" in block.lower()

    def test_exceptions_and_warnings_rendered(self) -> None:
        """A rule's exceptions and warnings reach the evidence block."""
        source_id = SourceId(uuid.uuid4())
        rule = make_rule(
            source_document_id=source_id,
            exceptions=("Greasy cans are not accepted",),
            warnings=("Do not crush before recycling",),
        )

        block = format_rule_context(
            [rule],
            {
                source_id: make_source_document(
                    id=source_id, url="https://x.example"
                )
            },
        )

        assert "Greasy cans are not accepted" in block
        assert "Do not crush before recycling" in block

    def test_multiple_rules_render_numbered_blocks(self) -> None:
        """Each retrieved rule gets its own numbered, source-bearing block."""
        sid1, sid2 = SourceId(uuid.uuid4()), SourceId(uuid.uuid4())
        rules = [
            make_rule(source_document_id=sid1),
            make_rule(
                source_document_id=sid2, accepted_status=AcceptedStatus.REJECTED
            ),
        ]
        sources = {
            sid1: make_source_document(id=sid1, url="https://a.example"),
            sid2: make_source_document(id=sid2, url="https://b.example"),
        }

        block = format_rule_context(rules, sources)

        assert "Rule 1:" in block
        assert "Rule 2:" in block
        assert "https://a.example" in block
        assert "https://b.example" in block

    def test_empty_rules_renders_none_marker(self) -> None:
        block = format_rule_context([], {})
        assert "none" in block.lower()
