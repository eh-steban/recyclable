"""GroundingValidator Specification (Level-2 whole-object check).

Runs after every Sonnet response on the retrieval path. Hard blocks convert
the response to NoEvaluation(reason=ValidatorRejected).

Calls check_grounding() from domain/retrieval/check_grounding.py -- the
single shared pure function (design D2).
"""

from dataclasses import dataclass

from src.domain.retrieval.check_grounding import check_grounding
from src.domain.retrieval.citation import Citation
from src.domain.retrieval.item_verdict import ItemVerdict, is_definitive


@dataclass(frozen=True, slots=True)
class GroundingViolation:
    """Structural description of a grounding violation.

    code identifies the invariant violated.
    message is a human-readable description for the audit record.
    """

    code: str
    message: str


class GroundingValidator:
    """Specification that checks a Sonnet response for grounding.

    Per services.md Principle 8: domain-normal failures are represented
    as return values, not exceptions.

    Usage::

        validator = GroundingValidator()
        violations = validator.validate(verdict, citations, retrieved_urls)
        if violations:
            # hard block -- convert to NoEvaluation
            ...
    """

    def validate(
        self,
        verdict: ItemVerdict,
        citations: list[Citation] | tuple[Citation, ...],
        retrieved_source_urls: frozenset[str],
    ) -> list[GroundingViolation]:
        """Validate a verdict + citation set against the grounding contract.

        Returns an empty list when the response is grounded.
        Returns one or more GroundingViolation values on violation.
        Never raises on a domain-normal failure.
        """
        if check_grounding(verdict, citations, retrieved_source_urls):
            return []

        violations: list[GroundingViolation] = []

        if is_definitive(verdict) and not citations:
            violations.append(
                GroundingViolation(
                    code="INV-PROD-001",
                    message=(
                        "Definitive verdict has no citations; "
                        "every definitive answer must cite a source."
                    ),
                )
            )

        if not is_definitive(verdict) and citations:
            violations.append(
                GroundingViolation(
                    code="INV-PROD-001",
                    message=(
                        "Non-definitive verdict carries citations; "
                        "NotCovered claims no evidence and must not cite."
                    ),
                )
            )

        for citation in citations:
            if citation.url not in retrieved_source_urls:
                violations.append(
                    GroundingViolation(
                        code="INV-LLM-002",
                        message=(
                            f"Citation URL not in retrieved source set: "
                            f"{citation.url!r}"
                        ),
                    )
                )

        return violations
