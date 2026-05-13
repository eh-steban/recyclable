"""AnswerAuditRecordValidator Specification (Level-2 whole-object check).

Runs inside the AnswerAuditRecord constructor as a last-line defense.
Enforces the same predicate as GroundingValidator -- INV-PROD-001 and
INV-LLM-002 -- by calling the single shared check_grounding() function
(design D2: one definition, two import sites).

A violation raises AnswerAuditRecordValidationError (defined in
domain/exceptions.py).
"""

from src.domain.retrieval.check_grounding import check_grounding
from src.domain.retrieval.citation import Citation
from src.domain.retrieval.item_verdict import ItemVerdict, is_definitive


def validate_answer_audit_record(
    verdict: ItemVerdict,
    citations: list[Citation] | tuple[Citation, ...],
    retrieved_source_urls: frozenset[str],
) -> list[str]:
    """Validate the grounding contract for an AnswerAuditRecord.

    Returns a list of violation descriptions. Empty list means valid.
    Never raises -- violations are returned as values.
    """
    if check_grounding(verdict, citations, retrieved_source_urls):
        return []

    violations: list[str] = []

    if is_definitive(verdict) and not citations:
        violations.append(
            "Definitive verdict has no citations (INV-PROD-001): every"
            + " definitive answer must cite a source."
        )

    for citation in citations:
        if citation.url not in retrieved_source_urls:
            violations.append(
                "Citation URL not in retrieved source set (INV-LLM-002): "
                + repr(citation.url)
            )

    return violations
