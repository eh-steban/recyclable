"""Static guard tests for the ingestion tool surface.

Verifies:
- The tool list passed to the SDK for ingestion contains no writer tool
  (INV-LLM-003).
- The model ID is pinned to claude-opus-4-7 (INV-LLM-005).

Story 1 asserts two-tool surface {fetch_source, extract_rules}.
Story 3 will tighten to exact three-tool {fetch_source, extract_rules,
diff_source}.
"""

from src.domain.ingestion.ingestion_llm import OPUS_MODEL_ID
from src.llm.prompts.extract_rules import (
    EXTRACT_RULES_VERSION,
    build_extract_rules_tool_schema,
)

_WRITER_PATTERNS = {
    "write",
    "update",
    "delete",
    "drop",
    "exec",
    "insert",
    "create",
    "modify",
    "patch",
    "put",
    "post",
    "upsert",
}


def _tool_names(tools: list[dict[str, object]]) -> set[str]:
    return {str(t.get("name", "")) for t in tools}


class TestIngestionToolSurface:
    def test_no_writer_tool_in_schema(self) -> None:
        """Tool schema must contain no writer tool (INV-LLM-003)."""
        schema = build_extract_rules_tool_schema()
        for tool in schema:
            name = str(tool.get("name", "")).lower()
            for pattern in _WRITER_PATTERNS:
                assert pattern not in name, (
                    f"Writer tool {name!r} found in ingestion schema -- "
                    f"matches pattern {pattern!r}"
                )

    def test_extract_rules_tool_present(self) -> None:
        """extract_rules tool must be in the schema."""
        schema = build_extract_rules_tool_schema()
        names = _tool_names(schema)
        assert "extract_rules" in names

    def test_fetch_source_tool_present(self) -> None:
        """fetch_source tool must be in the schema."""
        schema = build_extract_rules_tool_schema()
        names = _tool_names(schema)
        assert "fetch_source" in names

    def test_opus_model_id_pinned(self) -> None:
        """Ingestion LLM port must pin Opus model ID (INV-LLM-005)."""
        assert OPUS_MODEL_ID == "claude-opus-4-7"

    def test_extract_rules_version_is_int(self) -> None:
        """Prompt version must be a positive integer for audit traceability."""
        assert isinstance(EXTRACT_RULES_VERSION, int)
        assert EXTRACT_RULES_VERSION >= 1
