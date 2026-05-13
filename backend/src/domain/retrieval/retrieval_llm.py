"""RetrievalLLM port (Protocol).

The domain-side interface for the Sonnet LLM call on the user path.
The implementation lives in infra/external/anthropic_client.py.

INV-LLM-005: the model ID on the user path is claude-sonnet-4-6 (pinned).
"""

from typing import Protocol, TypedDict

from src.domain.retrieval.evaluated_answer import EvaluatedAnswer, NoEvaluation

#: The Sonnet model constant pinned for the user path (INV-LLM-005).
SONNET_MODEL_ID = "claude-sonnet-4-6"


class LLMMessage(TypedDict):
    """A single message in the Anthropic SDK message array.

    Both ``role`` and ``content`` are strings. The ``role`` field is
    always ``"user"`` on the user path; ``"assistant"`` may appear in
    multi-turn flows. Keeping the type in the domain layer avoids
    importing the Anthropic SDK here (forbidden by architecture rules).
    """

    role: str
    content: str


class RetrievalLLM(Protocol):
    """Port for the Sonnet LLM call on the retrieval path.

    Implemented in infra/external/anthropic_client.py.
    Accepts no Anthropic SDK types -- the domain layer never imports the SDK.
    """

    def ask(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
    ) -> EvaluatedAnswer | NoEvaluation:
        """Call the Sonnet model with the composed message array.

        Args:
            messages: composed message list from ask_compose_v1().
            system_prompt: the grounding contract + retrieved rule block.

        Returns:
            EvaluatedAnswer on a well-formed, grounded LLM response.
            NoEvaluation(reason=ValidatorRejected) when the LLM response
            fails JSON schema validation or grounding checks.
        """
        ...
