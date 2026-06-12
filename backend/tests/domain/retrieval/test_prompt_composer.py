"""Tests for ask_compose_v1 prompt composition.

Pins the three pieces the Sonnet user path depends on: the user turn
delimits the query (INV-LLM-004), the system prompt carries the
grounding contract + answer JSON schema, and the retrieved rule + source
block is rendered with the exact source URL the model must cite back
(INV-LLM-002).
"""

import uuid
from datetime import UTC, datetime

from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.material import MaterialId
from src.domain.knowledge_base.rule import (
    AcceptedStatus,
    Disposition,
    Rule,
    RuleId,
)
from src.domain.knowledge_base.source import SourceDocument, SourceId
from src.domain.retrieval.prompt_composer import (
    ask_compose_v1,
    format_rule_context,
)
from src.domain.retrieval.query import Query


def _make_rule(
    source_id: SourceId,
    accepted_status: AcceptedStatus = AcceptedStatus.ACCEPTED,
    *,
    exceptions: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
) -> Rule:
    return Rule(
        id=RuleId(uuid.uuid4()),
        jurisdiction_id=JurisdictionId(uuid.uuid4()),
        material_id=MaterialId(uuid.uuid4()),
        disposition=Disposition.CURBSIDE_RECYCLE,
        accepted_status=accepted_status,
        source_document_id=source_id,
        source_quote="Aluminum beverage cans are accepted curbside.",
        preparation_steps=("Empty and rinse the can",),
        exceptions=exceptions,
        warnings=warnings,
    )


def _make_source(source_id: SourceId, url: str) -> SourceDocument:
    return SourceDocument(
        id=source_id,
        jurisdiction_id=JurisdictionId(uuid.uuid4()),
        url=url,
        title="Denver Accepted-for-Recycling",
        authority_level=1,
        fetched_at=datetime.now(tz=UTC),
        source_text="Aluminum beverage cans are accepted curbside.",
        source_text_hash="hash",
    )


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
        # The model commits to a grounded verdict; not_covered is not offered
        # because the no-rule case is handled before the LLM is called.
        assert "not_covered" not in lowered
        assert "accepted" in lowered and "refused" in lowered
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
        rule = _make_rule(source_id)
        source = _make_source(source_id, url)

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
        rule = _make_rule(source_id)

        block = format_rule_context([rule], {})

        assert "source_url" not in block  # no citable URL emitted
        assert "http" not in block
        assert "unavailable" in block.lower()

    def test_exceptions_and_warnings_rendered(self) -> None:
        """A rule's exceptions and warnings reach the evidence block."""
        source_id = SourceId(uuid.uuid4())
        rule = _make_rule(
            source_id,
            exceptions=("Greasy cans are not accepted",),
            warnings=("Do not crush before recycling",),
        )

        block = format_rule_context(
            [rule], {source_id: _make_source(source_id, "https://x.example")}
        )

        assert "Greasy cans are not accepted" in block
        assert "Do not crush before recycling" in block

    def test_multiple_rules_render_numbered_blocks(self) -> None:
        """Each retrieved rule gets its own numbered, source-bearing block."""
        sid1, sid2 = SourceId(uuid.uuid4()), SourceId(uuid.uuid4())
        rules = [_make_rule(sid1), _make_rule(sid2, AcceptedStatus.REJECTED)]
        sources = {
            sid1: _make_source(sid1, "https://a.example"),
            sid2: _make_source(sid2, "https://b.example"),
        }

        block = format_rule_context(rules, sources)

        assert "Rule 1:" in block
        assert "Rule 2:" in block
        assert "https://a.example" in block
        assert "https://b.example" in block

    def test_empty_rules_renders_none_marker(self) -> None:
        block = format_rule_context([], {})
        assert "none" in block.lower()
