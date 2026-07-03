"""Anthropic SDK adapter.

Implements RetrievalLLM (Sonnet, user path), MaterialNormalizerLLM
(Haiku, normalizer fallback), and IngestionLLM (Opus, ingestion worker).

INV-LLM-005: model IDs are pinned as module-level constants.
No caller passes a model parameter.

reportAny / reportExplicitAny are disabled here: LLM JSON responses
are untyped at the SDK boundary; `Any` is the honest type until
schema validation is added.
"""

# pyright: reportAny=false, reportExplicitAny=false

import html
import json
import logging
import re
import time
import uuid
from collections.abc import Callable
from typing import Any, Final, cast, final

import anthropic
from anthropic.types import Message, MessageParam

from src.domain.ingestion.candidate_rule import CandidateRule
from src.domain.ingestion.ingestion_llm import OPUS_MODEL_ID
from src.domain.ingestion.source_fetcher import SourceFetchResult
from src.domain.knowledge_base.material import Material, MaterialId
from src.domain.retrieval.citation import Citation
from src.domain.retrieval.evaluated_answer import (
    EvaluatedAnswer,
    NoEvaluation,
    NoEvaluationReason,
)
from src.domain.retrieval.item_verdict import Accepted, Refused
from src.domain.retrieval.retrieval_llm import SONNET_MODEL_ID, LLMMessage
from src.llm.prompts.extract_rules import (
    build_extract_rules_system_prompt,
    build_extract_rules_tool_schema,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pinned model IDs (INV-LLM-005)
# ---------------------------------------------------------------------------

# SONNET_MODEL_ID (user path) is imported from the domain port, its single
# source of truth; HAIKU_MODEL_ID (normalizer fallback) is pinned locally.
HAIKU_MODEL_ID = "claude-haiku-4-5-20251001"

# Versioned name of the Haiku classify prompt, logged per call so traces
# map back to the exact prompt wording (llm rules: prompt name + version).
MATERIAL_NORMALIZE_PROMPT_VERSION = "material_normalize_v1"

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

            citations = tuple(
                Citation(
                    title=c.get("title", ""),
                    url=c.get("url", ""),
                    quote=c.get("quote"),
                )
                for c in citations_raw
                if c.get("url")
            )

            verdict = self._parse_verdict(verdict_str, payload, citations)
            if verdict is None:
                logger.warning(
                    "ask: model emitted non-grounded verdict %r", verdict_str
                )
                return NoEvaluation(
                    reason=NoEvaluationReason.VALIDATOR_REJECTED
                )

            return EvaluatedAnswer(
                verdict=verdict,
                recommended_action=recommended_action,
                confidence=confidence,
                # Empty here: the LLM port produces a candidate and does not
                # know the retrieved set. RetrievalService stamps the genuine
                # allow-list after grounding (INV-LLM-002).
                retrieved_source_urls=frozenset(),
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
        verdict_str: str,
        payload: dict[str, Any],
        citations: tuple[Citation, ...],
    ) -> Accepted | Refused | None:
        """Map a wire verdict string to a grounded ItemVerdict, or None.

        Only the two grounded verdicts are model-mintable. None signals an
        off-contract verdict (not_covered, conflicted, or anything
        unrecognized); the caller converts it to NoEvaluation.
        """
        conditions = payload.get("conditions", [])
        if verdict_str == "accepted":
            return Accepted(conditions=tuple(conditions), citations=citations)
        if verdict_str == "refused":
            return Refused(citations=citations)
        return None

    # ------------------------------------------------------------------
    # MaterialNormalizerLLM port
    # ------------------------------------------------------------------

    def classify(
        self,
        query_text: str,
        known_materials: list[Material],
    ) -> list[tuple[MaterialId, float]]:
        """Call Haiku to classify query_text against the known materials.

        Returns ranked (material_id, confidence) pairs for the materials
        the query plausibly refers to. Returns [] when no material fits
        or on any parse failure (the domain normalizer treats [] as
        Uncertain).
        """
        logger.info(
            "classify: Haiku model=%s prompt=%s query=%r candidates=%d",
            HAIKU_MODEL_ID,
            MATERIAL_NORMALIZE_PROMPT_VERSION,
            query_text[:60],
            len(known_materials),
        )
        catalog = [
            {
                "material_id": str(m.id),
                "name": m.canonical_name,
                "category": str(m.category),
            }
            for m in known_materials
        ]
        system_text = (
            "You are a recycling material classifier. You are given a "
            "user's query and a catalog of known materials, each with a "
            "material_id, name, and category. Identify which catalog "
            "materials the query refers to and score each by how "
            "confidently the query refers to it (0.0-1.0). Include ONLY "
            "materials the query plausibly refers to -- omit unrelated "
            "ones. If the query does not refer to any material in the "
            "catalog, return an empty array. "
            "Return only a JSON array: "
            '[{"material_id": "<id>", "confidence": 0.9}, ...]'
        )
        # User query and catalog are each delimited (INV-LLM-004), matching
        # the <user_query> convention of the ask path, so a crafted query
        # cannot forge catalog entries by escaping its tag.
        user_msg = (
            f"<user_query>{query_text}</user_query>\n"
            f"<catalog>{json.dumps(catalog)}</catalog>"
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

        return self._parse_classify_response(response, known_materials)

    def _parse_classify_response(
        self,
        response: Message,
        known_materials: list[Material],
    ) -> list[tuple[MaterialId, float]]:
        """Parse Haiku classify response into (MaterialId, float) pairs."""
        try:
            text = _first_text_block(response)
            if text is None:
                return []
            items: list[dict[str, Any]] = json.loads(_extract_json(text))
            id_map = {str(m.id): m.id for m in known_materials}
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


# ---------------------------------------------------------------------------
# OpusIngestionClient -- IngestionLLM port (INV-LLM-005, INV-LLM-003)
# ---------------------------------------------------------------------------


@final
class OpusIngestionClient:
    """Opus-powered IngestionLLM implementation.

    Makes one Anthropic SDK call per extract() invocation: passes the
    pre-fetched source text as the first user message, then drives
    the tool loop until Opus calls extract_rules or stops.

    The tool list is {fetch_source, extract_rules} -- no writer (INV-LLM-003).
    OPUS_MODEL_ID is imported from the domain port (INV-LLM-005).
    """

    _client: anthropic.Anthropic
    _timeout_s: float

    def __init__(
        self,
        api_key: str,
        *,
        timeout_s: float = 120.0,
    ) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._timeout_s = timeout_s

    def extract(
        self,
        source: SourceFetchResult,
        jurisdiction_id: str,
        jurisdiction_name: str,
        prompt_name: str,
        prompt_version: int,
    ) -> list[CandidateRule]:
        """Call Opus with the source text; return extracted CandidateRules.

        jurisdiction_name is the human-readable display name passed to the
        system prompt (INV-LLM-008); jurisdiction_id is used for tracing only.
        """
        tools = build_extract_rules_tool_schema()
        system_prompt = build_extract_rules_system_prompt(
            jurisdiction_name=jurisdiction_name
        )
        # Wrap source text in a delimiter to prevent prompt injection
        # (INV-LLM-004 convention from the retrieval path).
        # XML-escape the URL so special chars in query strings don't break
        # the attribute structure of the <source_document> tag.
        escaped_url = html.escape(source.url, quote=True)
        user_content = (
            f"Please extract recycling rules from the following source page"
            f" (source_document_id: {source.id}).\n\n"
            f'<source_document id="{source.id}" url="{escaped_url}">\n'
            f"{source.source_text[:200_000]}\n"
            f"</source_document>"
        )

        logger.info(
            "opus_extract: calling Opus model=%s prompt=%s/%d source=%r",
            OPUS_MODEL_ID,
            prompt_name,
            prompt_version,
            source.url,
        )
        start = time.monotonic()

        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_content}
        ]
        all_candidates: list[CandidateRule] = []

        # Drive the tool loop: Opus may call fetch_source (ignored in S1,
        # we return empty) or extract_rules (we capture candidates). Stop
        # when the model emits end_turn or no tool calls remain.
        for _turn in range(10):
            response: Message = self._client.messages.create(
                model=OPUS_MODEL_ID,
                max_tokens=4096,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                tools=cast("Any", tools),
                messages=cast("list[MessageParam]", messages),
                timeout=self._timeout_s,
            )

            # Append model turn to conversation.
            messages.append({"role": "assistant", "content": response.content})

            # Check for tool use.
            tool_calls = [b for b in response.content if b.type == "tool_use"]
            if not tool_calls:
                # No tool calls -- model is done.
                break

            # Build tool results for next turn.
            tool_results: list[dict[str, Any]] = []
            for tool_block in tool_calls:
                if tool_block.name == "extract_rules":
                    candidates = _parse_extract_rules_input(
                        cast("dict[str, Any]", tool_block.input),
                        jurisdiction_id,
                        source.id,
                    )
                    all_candidates.extend(candidates)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": "ok",
                        }
                    )
                else:
                    # fetch_source in S1: return empty (we pre-fetched).
                    _prefetched = "Source already provided."
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": _prefetched,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})

            if response.stop_reason == "end_turn":
                break

        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "opus_extract: done model=%s candidates=%d elapsed_ms=%d",
            OPUS_MODEL_ID,
            len(all_candidates),
            elapsed_ms,
        )
        return all_candidates


def _parse_extract_rules_input(
    tool_input: dict[str, Any],
    jurisdiction_id: str,
    source_id: uuid.UUID,
) -> list[CandidateRule]:
    """Parse the extract_rules tool input into CandidateRule list.

    Silently skips malformed candidates (logs a warning) so a single
    bad candidate doesn't drop the entire batch.
    """
    raw_id: str = tool_input.get("source_document_id", "")
    try:
        source_doc_id = uuid.UUID(raw_id)
    except ValueError, AttributeError, TypeError:
        logger.warning(
            "extract_rules: invalid source_document_id=%r; fallback=%s",
            raw_id,
            source_id,
        )
        source_doc_id = source_id

    candidates_raw: list[dict[str, Any]] = tool_input.get("candidates", [])
    results: list[CandidateRule] = []
    jur_uuid: uuid.UUID
    try:
        jur_uuid = uuid.UUID(jurisdiction_id)
    except ValueError:
        logger.warning(
            "extract_rules: non-UUID jurisdiction_id=%r; skipping candidates",
            jurisdiction_id,
        )
        return []

    for i, raw in enumerate(candidates_raw):
        try:
            results.append(
                CandidateRule(
                    source_document_id=source_doc_id,
                    source_quote=raw.get("source_quote", ""),
                    confidence=raw.get("confidence", "low"),
                    jurisdiction_id=jur_uuid,
                    material_slug=raw.get("material_slug", ""),
                    disposition=raw.get("disposition", "unknown"),
                    accepted_status=raw.get("accepted_status", "unknown"),
                    preparation_steps=tuple(raw.get("preparation_steps", [])),
                    exceptions=tuple(raw.get("exceptions", [])),
                    warnings=tuple(raw.get("warnings", [])),
                    effective_from=raw.get("effective_from"),
                )
            )
        except Exception as exc:
            logger.warning(
                "extract_rules: skipping malformed candidate[%d]: %s",
                i,
                exc,
            )

    return results
