"""IngestionLLM port -- the Opus-powered ingestion research surface.

INV-LLM-005: model pinned to claude-opus-4-7. The constant is declared here
(the domain port's single source of truth) and imported by the implementation
in anthropic_client.py.

Story 1 delivers a single-shot contract: fetch one page, extract candidates.
Story 3 will extend this to a bounded agentic loop.
"""

from typing import Final, Protocol

from src.domain.ingestion.candidate_rule import CandidateRule
from src.domain.ingestion.source_fetcher import SourceFetchResult

# Pinned Opus model ID for the ingestion research path (INV-LLM-005).
OPUS_MODEL_ID: Final[str] = "claude-opus-4-7"


class IngestionLLM(Protocol):
    """Port for the Opus-powered single-page extraction (Story 1 contract).

    The implementation makes a single Anthropic SDK call with the
    {fetch_source, extract_rules} tool set and returns the extracted
    candidates. No writer tools may appear in the tool list (INV-LLM-003).
    """

    def extract(
        self,
        source: SourceFetchResult,
        jurisdiction_id: str,
        prompt_name: str,
        prompt_version: int,
    ) -> list[CandidateRule]: ...
