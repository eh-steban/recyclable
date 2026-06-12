"""PromptComposer -- the versioned ``ask_compose_v1`` user-path prompt.

``ask_compose_v1`` is the whole prompt: a system block carrying the
grounding contract, the answer JSON schema, and the retrieved rule +
source block, plus a user turn carrying the raw query. The user query is
wrapped in ``<user_query>...</user_query>`` delimiters and never
concatenated into the system block (INV-LLM-004).

The retrieved rule + source block is the model's only evidence: it must
cite the source URLs verbatim from that block, and the GroundingValidator
rejects any citation URL that is not in it (INV-LLM-002).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from src.domain.knowledge_base.rule import Rule
from src.domain.knowledge_base.source import SourceDocument, SourceId
from src.domain.retrieval.query import Query
from src.domain.retrieval.retrieval_llm import LLMMessage

# ---------------------------------------------------------------------------
# Grounding contract -- the static system-prompt prefix (cacheable).
# ---------------------------------------------------------------------------

#: Instructions + answer JSON schema prepended to every user-path system
#: prompt. Static so the Anthropic prompt cache can reuse the prefix; the
#: per-query rule context is appended after it.
GROUNDING_CONTRACT = """\
You are Recyclable, a grounded recycling-rules assistant. Answer whether and \
how a specific material can be recycled in a specific jurisdiction, using ONLY \
the rules and sources in the RETRIEVED RULES block of this prompt.

Grounding rules (absolute):
1. Use only the RETRIEVED RULES block. Never rely on outside knowledge, never \
guess, and never state a rule that is not present there.
2. Every definitive answer (verdict "accepted" or "refused") MUST include at \
least one citation drawn from the RETRIEVED RULES block.
3. Copy each citation's "url" and "title" verbatim from the block. Never \
invent, edit, shorten, or complete a URL. A citation whose URL is not in the \
block is discarded and the answer is rejected.
4. The RETRIEVED RULES block contains the governing rule for this item; \
base your verdict on its status.

Verdict selection, from the rule's status in the block:
- status "accepted"    -> verdict "accepted" with an empty "conditions" list.
- status "conditional" -> verdict "accepted" and list each precondition (for \
example "Empty and rinse") as a string in "conditions".
- status "rejected"    -> verdict "refused".

Respond with ONLY a single JSON object (no prose, no markdown fence) of this \
exact shape:
{
  "verdict": "accepted" | "refused",
  "conditions": [string],
  "recommended_action": string,
  "confidence": "high" | "medium" | "low",
  "citations": [{"title": string, "url": string, "quote": string}],
  "preparation_steps": [string],
  "do_not_do": [string],
  "clarifying_question": string | null
}

Field rules:
- "recommended_action": one concise next step for the user, at most 500 \
characters.
- "citations": exactly the sources you used; "quote" is a short snippet copied \
from that rule's source text. Never empty -- every verdict cites the rule it \
relied on.
- "confidence": your confidence that the cited rule answers the question.
- "preparation_steps" / "do_not_do": may be empty lists.
- "clarifying_question": null unless you must ask the user to clarify."""


# ---------------------------------------------------------------------------
# Composed prompt
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ComposedPrompt:
    """The fully composed ask_compose_v1 prompt.

    system_prompt is routed to the Anthropic SDK ``system=`` parameter;
    messages is the role-separated user turn. Keeping them separate is what
    enforces INV-LLM-004: user text only ever lands in ``messages``.
    """

    system_prompt: str
    messages: tuple[LLMMessage, ...]


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


def format_rule_context(
    rules: list[Rule],
    sources_by_id: Mapping[SourceId, SourceDocument],
) -> str:
    """Render the retrieved rules + their sources as the evidence block.

    Each rule is rendered with its status, disposition, source quote, and
    -- when its SourceDocument is available -- the verbatim source title and
    URL the model must cite. A rule whose source is missing is flagged
    uncitable and contributes no URL, so the model cannot fabricate one
    (INV-LLM-002).
    """
    if not rules:
        return "RETRIEVED RULES:\n(none)"

    blocks: list[str] = []
    for index, rule in enumerate(rules, start=1):
        lines = [
            f"Rule {index}:",
            f"  status: {rule.accepted_status.value}",
            f"  disposition: {rule.disposition.value}",
            f'  source_quote: "{rule.source_quote}"',
        ]
        if rule.preparation_steps:
            lines.append(
                f"  preparation_steps: {'; '.join(rule.preparation_steps)}"
            )
        if rule.exceptions:
            lines.append(f"  exceptions: {'; '.join(rule.exceptions)}")
        if rule.warnings:
            lines.append(f"  warnings: {'; '.join(rule.warnings)}")

        source = sources_by_id.get(rule.source_document_id)
        if source is not None:
            lines.append(f'  source_title: "{source.title}"')
            lines.append(f"  source_url: {source.url}")
        else:
            lines.append("  source: unavailable -- do not cite this rule")

        blocks.append("\n".join(lines))

    return "RETRIEVED RULES:\n" + "\n\n".join(blocks)


def ask_compose_v1(query: Query, rule_context: str) -> ComposedPrompt:
    """Compose the user-path prompt (system block + user turn).

    Args:
        query: the validated Query Value.
        rule_context: the retrieved rule + source block from
            format_rule_context(), appended to the grounding contract to
            form the system prompt.

    Returns:
        A ComposedPrompt whose system_prompt carries the grounding contract
        + answer schema + rule context, and whose messages carry the
        delimited user query.
    """
    system_prompt = f"{GROUNDING_CONTRACT}\n\n{rule_context}"
    user_content = (
        f"<user_query>{query.text}</user_query>\n\n"
        f"Location: {query.location_input}"
    )
    return ComposedPrompt(
        system_prompt=system_prompt,
        messages=({"role": "user", "content": user_content},),
    )
