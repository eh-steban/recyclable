"""Anthropic SDK adapter.

Implements both RetrievalLLM (Sonnet, user path) and
MaterialNormalizerLLM (Haiku, normalizer fallback).

INV-LLM-005: model IDs are pinned as module-level constants.
No caller passes a model parameter.

reportAny / reportExplicitAny are disabled here: LLM JSON responses
are untyped at the SDK boundary; `Any` is the honest type until
schema validation is added.
"""

# pyright: reportAny=false, reportExplicitAny=false

import json
import logging
import re
import time
from collections.abc import Callable
from typing import Any, Final, cast, final

import anthropic
from anthropic.types import Message, MessageParam

from src.domain.knowledge_base.material import MaterialId
from src.domain.retrieval.citation import Citation
from src.domain.retrieval.evaluated_answer import (
    EvaluatedAnswer,
    NoEvaluation,
    NoEvaluationReason,
)
from src.domain.retrieval.item_verdict import (
    Accepted,
    Conflicted,
    ItemVerdict,
    NotCovered,
    Refused,
)
from src.domain.retrieval.retrieval_llm import LLMMessage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pinned model IDs (INV-LLM-005)
# ---------------------------------------------------------------------------

SONNET_MODEL_ID = "claude-sonnet-4-6"
HAIKU_MODEL_ID = "claude-haiku-4-5-20251001"

# ---------------------------------------------------------------------------
# Destructive-tool guard
# ---------------------------------------------------------------------------

_DESTRUCTIVE_RE = re.compile(
    r"write|update|delete|drop|exec|insert", re.IGNORECASE
)


def _assert_no_destructive_tools(tools: list[dict[str, object]]) -> None:
    """Raise ValueError if any tool name matches the destructive-op pattern."""
    for tool in tools:
        name = str(tool.get("name", ""))
        if _DESTRUCTIVE_RE.search(name):
            msg = (
                f"Tool name {name!r} matches destructive-op pattern; only "
                + "read-only tools are permitted in the retrieval client."
            )
            raise ValueError(msg)


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

_RETRYABLE_STATUS: Final = frozenset({429, 500, 502, 503, 504})


def _call_with_retry(
    fn: Callable[[], Message], max_retries: int = 1
) -> Message:
    """Call fn(); retry once on retryable Anthropic status errors."""
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except anthropic.APIStatusError as exc:
            if attempt < max_retries and exc.status_code in _RETRYABLE_STATUS:
                logger.warning(
                    "Anthropic API status %s, retrying (attempt %d)",
                    exc.status_code,
                    attempt + 1,
                )
                time.sleep(0.5 * (attempt + 1))
                continue
            raise
    raise RuntimeError("unreachable: _call_with_retry exhausted loop")


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _first_text_block(response: Message) -> str | None:
    """Return the text content of the first text block in response, or None."""
    for block in response.content:
        if block.type == "text":
            return block.text
    return None


def _extract_json(text: str) -> str:
    """Extract a JSON payload from an LLM text block.

    Claude commonly wraps JSON in a ```json ... ``` fence and may append
    prose after the closing fence. Return the fenced contents when a fence
    is present; otherwise return the stripped text unchanged so a bare JSON
    body still parses.
    """
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.DOTALL)
    if fence is not None:
        return fence.group(1).strip()
    return stripped


# ---------------------------------------------------------------------------
# AnthropicClient
# ---------------------------------------------------------------------------


@final
class AnthropicClient:
    """Anthropic SDK adapter implementing RetrievalLLM + MaterialNormalizerLLM.

    Constructor args:
        api_key: Anthropic API key.
        timeout_s: per-request timeout in seconds (default 20.0).
        tool_registry: optional list of tool dicts; checked for destructive
                       names at construction time.
    """

    _client: anthropic.Anthropic
    _timeout_s: float
    _tool_registry: list[dict[str, object]]

    def __init__(
        self,
        api_key: str,
        *,
        timeout_s: float = 20.0,
        tool_registry: list[dict[str, object]] | None = None,
    ) -> None:
        if tool_registry:
            _assert_no_destructive_tools(tool_registry)
        self._client = anthropic.Anthropic(api_key=api_key)
        self._timeout_s = timeout_s
        self._tool_registry = tool_registry or []

    # ------------------------------------------------------------------
    # RetrievalLLM port
    # ------------------------------------------------------------------

    def ask(
        self,
        messages: list[LLMMessage],
        system_prompt: str,
    ) -> EvaluatedAnswer | NoEvaluation:
        """Call Sonnet with prompt-cached system block; parse into domain type.

        Accepts the domain's SDK-free LLMMessage type (the port forbids
        Anthropic SDK types in the domain layer); the cast to the SDK's
        MessageParam is the adapter-boundary translation.

        Returns EvaluatedAnswer on a well-formed JSON response that passes
        basic field checks. Returns NoEvaluation on any parse failure.
        """
        logger.info(
            "ask: calling Sonnet model=%s messages=%d",
            SONNET_MODEL_ID,
            len(messages),
        )
        start = time.monotonic()
        try:
            response: Message = _call_with_retry(
                lambda: self._client.messages.create(
                    model=SONNET_MODEL_ID,
                    max_tokens=1024,
                    system=[
                        {
                            "type": "text",
                            "text": system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=cast("list[MessageParam]", messages),
                    timeout=self._timeout_s,
                )
            )
        except anthropic.APIStatusError as exc:
            logger.error(
                "ask: Anthropic API error status=%s: %s",
                exc.status_code,
                exc.message,
            )
            # INV-PROD-004: LLM unavailability is LLM_REJECTED, not
            # VALIDATOR_REJECTED. The model did not produce output -- no
            # validation took place. Auditing distinguishes the two.
            return NoEvaluation(reason=NoEvaluationReason.LLM_REJECTED)
        except Exception as exc:
            logger.error("ask: unexpected error calling Sonnet: %s", exc)
            return NoEvaluation(reason=NoEvaluationReason.LLM_REJECTED)

        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info("ask: Sonnet responded in %dms", elapsed_ms)

        return self._parse_ask_response(response)

    def _parse_ask_response(
        self, response: Message
    ) -> EvaluatedAnswer | NoEvaluation:
        """Parse the raw SDK response into a domain EvaluatedAnswer.

        Degrades to NoEvaluation on any JSON or schema mismatch.
        """
        try:
            text = _first_text_block(response)
            if text is None:
                logger.warning("ask: response has no text block")
                return NoEvaluation(
                    reason=NoEvaluationReason.VALIDATOR_REJECTED
                )

            payload: dict[str, Any] = json.loads(_extract_json(text))

            # Extract mandatory fields; fall back to NoEvaluation on error.
            verdict_str: str = payload.get("verdict", "")
            recommended_action: str = payload.get("recommended_action", "")
            confidence: str = payload.get("confidence", "low")
            citations_raw: list[Any] = payload.get("citations", [])

            verdict = self._parse_verdict(verdict_str, payload)
            citations = tuple(
                Citation(
                    title=c.get("title", ""),
                    url=c.get("url", ""),
                    quote=c.get("quote"),
                )
                for c in citations_raw
                if c.get("url")
            )

            return EvaluatedAnswer(
                verdict=verdict,
                citations=citations,
                recommended_action=recommended_action,
                confidence=confidence,
                preparation_steps=tuple(payload.get("preparation_steps", [])),
                do_not_do=tuple(payload.get("do_not_do", [])),
                clarifying_question=payload.get("clarifying_question"),
            )

        except (
            json.JSONDecodeError,
            KeyError,
            TypeError,
            AttributeError,
        ) as exc:
            logger.warning("ask: failed to parse Sonnet response: %s", exc)
            return NoEvaluation(reason=NoEvaluationReason.VALIDATOR_REJECTED)

    @staticmethod
    def _parse_verdict(
        verdict_str: str, payload: dict[str, Any]
    ) -> ItemVerdict:
        """Map wire verdict string to domain ItemVerdict variant."""
        conditions = payload.get("conditions", [])
        if verdict_str == "accepted":
            return Accepted(conditions=tuple(conditions))
        if verdict_str == "refused":
            return Refused()
        if verdict_str == "not_covered":
            return NotCovered()
        if verdict_str == "conflicted":
            return Conflicted()
        # Unknown verdict -- default to NotCovered (no evidence).
        return NotCovered()

    # ------------------------------------------------------------------
    # MaterialNormalizerLLM port
    # ------------------------------------------------------------------

    def classify(
        self,
        query_text: str,
        known_material_ids: list[MaterialId],
    ) -> list[tuple[MaterialId, float]]:
        """Call Haiku to classify query_text against known material IDs.

        Returns ranked (material_id, confidence) pairs. Returns [] on
        any parse failure (domain normalizer treats [] as Uncertain).
        """
        logger.info(
            "classify: calling Haiku model=%s query=%r candidates=%d",
            HAIKU_MODEL_ID,
            query_text[:60],
            len(known_material_ids),
        )
        id_strs = [str(mid) for mid in known_material_ids]
        system_text = (
            "You are a recycling material classifier. "
            "Given a user query, rank the provided material IDs by "
            "relevance (0.0-1.0 confidence). "
            "Return a JSON array: "
            '[{"material_id": "<uuid>", "confidence": 0.9}, ...]'
        )
        user_msg = (
            f"Query: {query_text}\nKnown material IDs: {json.dumps(id_strs)}"
        )

        try:
            response: Message = _call_with_retry(
                lambda: self._client.messages.create(
                    model=HAIKU_MODEL_ID,
                    max_tokens=512,
                    system=[
                        {
                            "type": "text",
                            "text": system_text,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[{"role": "user", "content": user_msg}],
                    timeout=self._timeout_s,
                )
            )
        except Exception as exc:
            logger.error("classify: error calling Haiku: %s", exc)
            return []

        return self._parse_classify_response(response, known_material_ids)

    def _parse_classify_response(
        self,
        response: Message,
        known_material_ids: list[MaterialId],
    ) -> list[tuple[MaterialId, float]]:
        """Parse Haiku classify response into (MaterialId, float) pairs."""
        try:
            text = _first_text_block(response)
            if text is None:
                return []
            items: list[dict[str, Any]] = json.loads(_extract_json(text))
            id_map = {str(mid): mid for mid in known_material_ids}
            results: list[tuple[MaterialId, float]] = []
            for item in items:
                mid_str = item.get("material_id", "")
                conf = float(item.get("confidence", 0.0))
                if mid_str in id_map:
                    results.append((id_map[mid_str], conf))
            return sorted(results, key=lambda t: t[1], reverse=True)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("classify: failed to parse Haiku response: %s", exc)
            return []
