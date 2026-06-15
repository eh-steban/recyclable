"""Short-circuit doubles for the user-path LLM and material normalizer.

For a configurable answer use ``FakeAnthropicClient`` (it records calls and
serves a canned result); these two cover what it does not -- a
``RetrievalLLM`` that must never be reached, and a ``MaterialNormalizer``
stub.
"""

from typing import final

from src.domain.knowledge_base.normalization_result import NormalizationResult
from src.domain.retrieval.evaluated_answer import EvaluatedAnswer, NoEvaluation
from src.domain.retrieval.retrieval_llm import LLMMessage


@final
class NeverCalledLLM:
    """RetrievalLLM double that raises if ``ask`` is reached.

    Inject on pre-LLM short-circuit paths (out-of-jurisdiction, ambiguous,
    uncertain material). ``call_count`` stays 0 on a successful short-circuit;
    the retrieval-service tests assert that directly.
    """

    def __init__(self) -> None:
        self.call_count = 0

    def ask(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
    ) -> EvaluatedAnswer | NoEvaluation:
        self.call_count += 1
        raise AssertionError("RetrievalLLM must not be called on this path")


@final
class StubNormalizer:
    def __init__(self, result: NormalizationResult) -> None:
        self._result = result

    def normalize(self, query_text: str) -> NormalizationResult:
        return self._result
