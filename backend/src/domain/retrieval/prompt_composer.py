"""PromptComposer -- ask_compose_v1 prompt template.

Wraps the user-supplied query text in <user_query>...</user_query>
delimiters per INV-LLM-004. User text is never concatenated into the
system-prompt instruction block.

The composed message structure is a list of Anthropic-SDK-compatible
message dicts: [{"role": "user", "content": "..."}].
"""

from src.domain.retrieval.query import Query
from src.domain.retrieval.retrieval_llm import LLMMessage


def ask_compose_v1(query: Query, rule_context: str) -> list[LLMMessage]:
    """Compose the user-path message array for the Anthropic SDK.

    The system prompt (rule_context) must be passed separately to the
    Anthropic SDK via the `system=` parameter; this function returns only
    the messages list.

    The user turn wraps query.text in explicit XML delimiters so the LLM
    can distinguish user-supplied text from instructions. This implements
    INV-LLM-004: user input does not control the system prompt.

    Args:
        query: the validated Query Value.
        rule_context: the retrieved rule + source block (injected into the
            system prompt by the caller, not into this messages list).

    Returns:
        A list of message dicts compatible with the Anthropic SDK's
        ``messages`` parameter.
    """
    # rule_context is intentionally not consumed here: by design the
    # caller routes it to the Anthropic SDK `system=` parameter (see
    # docstring), so this composition step never reads it. Bound to `_`
    # to record that as deliberate -- not a forgotten wire-up. The
    # caller-side system-prompt injection is the integration point.
    _ = rule_context
    user_content = (
        f"<user_query>{query.text}</user_query>\n\n"
        f"Location: {query.location_input}"
    )
    return [{"role": "user", "content": user_content}]
