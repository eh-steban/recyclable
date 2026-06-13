"""check_grounding -- single shared pure grounding predicate.

Design D2: both GroundingValidator (domain/retrieval/) and
AnswerAuditRecordValidator (domain/audit/) import this function.
One definition, two import sites -- prevents drift between the two
Specifications (per private/specs/designs/01-sonnet-user-path.design.md).

Enforces:
- INV-PROD-001: definitive verdicts require at least one citation.
- INV-LLM-002: every citation URL must be in the retrieved source set.
"""

from src.domain.retrieval.item_verdict import (
    ItemVerdict,
    citations_of,
    is_definitive,
)


def check_grounding(
    verdict: ItemVerdict,
    retrieved_source_urls: frozenset[str],
) -> bool:
    """Return True when verdict satisfies the grounding contract.

    A verdict is grounded when:
    1. If the verdict is non-definitive (NotCovered): always grounded --
       NotCovered structurally carries no citations.
    2. If the verdict is definitive (Accepted / Refused / Conflicted):
       - citations is non-empty (INV-PROD-001).
       - every citation.url is a member of retrieved_source_urls
         (INV-LLM-002).

    Returns False on any violation; does not raise.
    """
    if not is_definitive(verdict):
        # NotCovered structurally carries no citations.
        return True

    citations = citations_of(verdict)

    # Definitive verdict: must have at least one citation (INV-PROD-001).
    if not citations:
        return False

    # Every citation URL must be in the retrieved source set (INV-LLM-002).
    return all(c.url in retrieved_source_urls for c in citations)
