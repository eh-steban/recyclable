"""Unit tests for _parse_extract_rules_input (B-2: provenance fallback).

Verifies that when the model's source_document_id is missing or unparseable,
the function falls back to the real source id (INV-DATA-001) rather than
minting a fresh UUID that fabricates provenance.
"""

import uuid

from src.infra.external.anthropic_client import _parse_extract_rules_input

_JURISDICTION_ID = str(uuid.uuid4())
_SOURCE_ID = uuid.uuid4()


class TestParseExtractRulesInputProvenance:
    def test_valid_source_document_id_used_as_is(self) -> None:
        """A valid UUID in the tool input is used for source_document_id."""
        doc_id = uuid.uuid4()
        tool_input = {
            "source_document_id": str(doc_id),
            "candidates": [
                {
                    "source_quote": "Glass is accepted.",
                    "confidence": "high",
                    "material_slug": "glass",
                    "disposition": "curbside_recycle",
                    "accepted_status": "accepted",
                }
            ],
        }
        results = _parse_extract_rules_input(
            tool_input, _JURISDICTION_ID, _SOURCE_ID
        )
        assert len(results) == 1
        assert results[0].source_document_id == doc_id

    def test_missing_source_document_id_falls_back_to_source_id(self) -> None:
        """Missing source_document_id falls back to the real source id."""
        tool_input = {
            "candidates": [
                {
                    "source_quote": "Glass is accepted.",
                    "confidence": "high",
                    "material_slug": "glass",
                    "disposition": "curbside_recycle",
                    "accepted_status": "accepted",
                }
            ],
        }
        results = _parse_extract_rules_input(
            tool_input, _JURISDICTION_ID, _SOURCE_ID
        )
        assert len(results) == 1
        assert results[0].source_document_id == _SOURCE_ID

    def test_invalid_source_document_id_falls_back_to_source_id(self) -> None:
        """Unparseable source_document_id falls back to the real source id."""
        tool_input = {
            "source_document_id": "not-a-uuid",
            "candidates": [
                {
                    "source_quote": "Cardboard is accepted.",
                    "confidence": "medium",
                    "material_slug": "cardboard",
                    "disposition": "curbside_recycle",
                    "accepted_status": "accepted",
                }
            ],
        }
        results = _parse_extract_rules_input(
            tool_input, _JURISDICTION_ID, _SOURCE_ID
        )
        assert len(results) == 1
        assert results[0].source_document_id == _SOURCE_ID

    def test_invalid_id_does_not_mint_random_uuid(self) -> None:
        """Fallback must use the known source id, never a random UUID."""
        other_source_id = uuid.uuid4()
        tool_input = {
            "source_document_id": "",
            "candidates": [
                {
                    "source_quote": "Plastic bags are not accepted.",
                    "confidence": "high",
                    "material_slug": "plastic-bags",
                    "disposition": "reject",
                    "accepted_status": "rejected",
                }
            ],
        }
        results = _parse_extract_rules_input(
            tool_input, _JURISDICTION_ID, _SOURCE_ID
        )
        assert len(results) == 1
        assert results[0].source_document_id == _SOURCE_ID
        assert results[0].source_document_id != other_source_id
