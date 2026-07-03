"""extract_rules prompt and tool schema for the ingestion Opus agent.

The tool schema is used in two ways:
1. Passed to the Anthropic SDK as the `tools` list for the Opus call.
2. Inspected by the static no-writer guard in tests (INV-LLM-003).
"""

# pyright: reportExplicitAny=false, reportAny=false
from typing import Any, Final

# Bump when any wording, schema, or example changes.
EXTRACT_RULES_VERSION: Final[int] = 1

# Stable prompt name for audit traces.
EXTRACT_RULES_PROMPT_NAME: Final[str] = "extract_rules_v1"

# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

# fetch_source tool: tells Opus to signal which URL it wants fetched.
# The implementation intercepts this tool call and performs the actual HTTP
# fetch via HttpSourceFetcher (SSRF-controlled). Opus never fetches directly.
_FETCH_SOURCE_TOOL: dict[str, Any] = {
    "name": "fetch_source",
    "description": (
        "Fetch the text content of a recycling-related URL. The system will"
        " retrieve the page and return its normalized text to you. Only call"
        " this with authoritative government or municipal URLs."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The HTTPS URL of the source page to fetch.",
            }
        },
        "required": ["url"],
    },
}

# extract_rules tool: Opus calls this to emit its structured extraction.
# The implementation validates the proposed candidates against the
# source_document before accepting them. A candidate with no source_quote
# raises FetchError at the tool-call handler boundary.
_EXTRACT_RULES_TOOL: dict[str, Any] = {
    "name": "extract_rules",
    "description": (
        "Record the recycling rules you have extracted from a source document."
        " Call this once per source document after reading it. Every rule"
        " MUST include a verbatim source_quote from the document."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "source_document_id": {
                "type": "string",
                "description": "UUID of the source document being cited.",
            },
            "candidates": {
                "type": "array",
                "description": "Array of extracted recycling rules.",
                "items": {
                    "type": "object",
                    "properties": {
                        "material_slug": {
                            "type": "string",
                            "description": "Material slug (e.g. glass-bottles)",
                        },
                        "disposition": {
                            "type": "string",
                            "enum": [
                                "curbside_recycle",
                                "dropoff",
                                "compost",
                                "landfill",
                                "hazardous_waste",
                                "donate",
                                "unknown",
                            ],
                        },
                        "accepted_status": {
                            "type": "string",
                            "enum": [
                                "accepted",
                                "rejected",
                                "conditional",
                                "unknown",
                            ],
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": (
                                "high: official municipal source + exact"
                                " match. medium: official + category match."
                                " low: third-party or ambiguous."
                            ),
                        },
                        "source_quote": {
                            "type": "string",
                            "description": (
                                "Verbatim exact text from the source that"
                                " justifies this rule. Required -- never empty."
                            ),
                        },
                        "preparation_steps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                        "exceptions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                        "warnings": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                        "effective_from": {
                            "type": "string",
                            "description": "ISO date string or null.",
                            "default": None,
                        },
                    },
                    "required": [
                        "material_slug",
                        "disposition",
                        "accepted_status",
                        "confidence",
                        "source_quote",
                    ],
                },
            },
        },
        "required": ["source_document_id", "candidates"],
    },
}


def build_extract_rules_tool_schema() -> list[dict[str, Any]]:
    """Return the tool list for the Opus ingestion call.

    Tools: {fetch_source, extract_rules} -- no writer (INV-LLM-003).
    """
    return [_FETCH_SOURCE_TOOL, _EXTRACT_RULES_TOOL]


def build_extract_rules_system_prompt(jurisdiction_name: str) -> str:
    """Build the system prompt for the extract_rules_v1 agent.

    The jurisdiction_name is stable across the agent turn and belongs in the
    cached system block (llm/CLAUDE.md § Prompt caching).
    """
    return (
        f"You are a recycling research assistant extracting recycling rules"
        f" for {jurisdiction_name}. Your job is to read official recycling"
        f" guidance pages and extract structured rules.\n\n"
        f"For each source page:\n"
        f"1. Identify all recycling rules (what is accepted, rejected, or"
        f" conditionally accepted at curbside, drop-off, etc.).\n"
        f"2. For each rule, cite the exact verbatim text from the source"
        f" (source_quote). Never leave source_quote empty.\n"
        f"3. Call extract_rules with all candidates from that page.\n\n"
        f"Confidence tiers:\n"
        f"- high: official municipal source (government domain) + exact"
        f" material name match.\n"
        f"- medium: official source + category-level match.\n"
        f"- low: third-party source or ambiguous attribution.\n\n"
        f"You have access to fetch_source to retrieve additional pages if"
        f" needed. Only fetch authoritative government or municipal URLs."
    )
