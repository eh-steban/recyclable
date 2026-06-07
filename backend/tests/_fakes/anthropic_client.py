"""In-memory fake for AnthropicClient.

Implements both LLM ports the real adapter serves -- ``RetrievalLLM.ask``
(Sonnet user path) and ``MaterialNormalizerLLM.classify`` (Haiku
fallback) -- so the full ``/ask`` pipeline runs offline and
deterministically, with no network and no cost.

A test configures what the model "answers"; the assertions belong on what
the pipeline *does* with that answer (grounding, audit, wire mapping), not
on the canned answer itself. ``ask_result`` and ``classify_result`` accept
either a fixed value or a callable, so a test can compute the answer from
the call arguments (e.g. cite a URL drawn from the prompt context to be
grounded by construction).
"""

from collections.abc import Callable

from src.domain.knowledge_base.material import Material, MaterialId
from src.domain.retrieval.evaluated_answer import EvaluatedAnswer, NoEvaluation
from src.domain.retrieval.retrieval_llm import LLMMessage

AskResult = EvaluatedAnswer | NoEvaluation
AskHandler = Callable[[list[LLMMessage], str], AskResult]
ClassifyRanking = list[tuple[MaterialId, float]]
ClassifyHandler = Callable[[str, list[Material]], ClassifyRanking]


class FakeAnthropicClient:
    """Configurable stand-in for AnthropicClient (both LLM ports).

    Records every call so a test can assert what the pipeline sent (and,
    for the out-of-jurisdiction path, that the model was never called).
    """

    def __init__(
        self,
        ask_result: AskResult | AskHandler,
        classify_result: ClassifyRanking | ClassifyHandler | None = None,
    ) -> None:
        self._ask_result: AskResult | AskHandler = ask_result
        self._classify_result: ClassifyRanking | ClassifyHandler = (
            classify_result if classify_result is not None else []
        )
        self.ask_calls: list[tuple[list[LLMMessage], str]] = []
        self.classify_calls: list[tuple[str, list[Material]]] = []

    def ask(self, messages: list[LLMMessage], system_prompt: str) -> AskResult:
        self.ask_calls.append((messages, system_prompt))
        if callable(self._ask_result):
            return self._ask_result(messages, system_prompt)
        return self._ask_result

    def classify(
        self, query_text: str, known_materials: list[Material]
    ) -> ClassifyRanking:
        self.classify_calls.append((query_text, known_materials))
        if callable(self._classify_result):
            return self._classify_result(query_text, known_materials)
        return self._classify_result
