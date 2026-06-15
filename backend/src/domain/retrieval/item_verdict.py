"""ItemVerdict sum type and its variants.

The domain verdict produced by the LLM and validated by GroundingValidator.
Citations are carried by the definitive variants (Accepted, Refused,
Conflicted). NotCovered structurally carries no citations -- use
citations_of() for a uniform accessor.
"""

from dataclasses import dataclass, field
from typing import assert_never, cast

from src.domain.retrieval.citation import Citation


@dataclass(frozen=True, slots=True)
class Accepted:
    """The material is accepted under the queried jurisdiction's rules.

    conditions is an ordered list of prerequisite requirements (e.g. "Empty
    and rinse"). When non-empty, the wire layer renders
    short_answer = 'conditional'.

    citations: sources that support the verdict (INV-PROD-001).
    """

    conditions: tuple[str, ...] = field(default_factory=tuple)
    citations: tuple[Citation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        # Runtime boundary guard: cast(object, ...) keeps this a real check
        # despite the declared tuple type. See private/learnings.md
        # (tuple boundary-guard idiom).
        if not isinstance(cast(object, self.conditions), tuple):
            kind = type(self.conditions).__name__
            raise TypeError(f"Accepted.conditions must be a tuple, got {kind}")
        if not isinstance(cast(object, self.citations), tuple):
            kind = type(self.citations).__name__
            raise TypeError(f"Accepted.citations must be a tuple, got {kind}")


@dataclass(frozen=True, slots=True)
class Refused:
    """The material is definitively refused/rejected.

    The LLM has determined the rule denies this material. Citations are
    required by INV-PROD-001.
    """

    citations: tuple[Citation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(cast(object, self.citations), tuple):
            kind = type(self.citations).__name__
            raise TypeError(f"Refused.citations must be a tuple, got {kind}")


@dataclass(frozen=True, slots=True)
class NotCovered:
    """No rule found for this (jurisdiction, material) tuple.

    Maps to short_answer = 'unknown'. No Anthropic call is made;
    the application service produces this without consulting the LLM.
    Structurally carries no citations.
    """

    pass


@dataclass(frozen=True, slots=True)
class Conflicted:
    """Multiple sources disagree on this rule.

    The retrieval service surfaces the conflict. Citations are required
    (INV-PROD-001).
    """

    citations: tuple[Citation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(cast(object, self.citations), tuple):
            kind = type(self.citations).__name__
            raise TypeError(f"Conflicted.citations must be a tuple, got {kind}")


#: The ItemVerdict sum type.
ItemVerdict = Accepted | Refused | NotCovered | Conflicted


def is_definitive(verdict: ItemVerdict) -> bool:
    """Return True when a verdict requires citations (INV-PROD-001).

    Definitive verdicts are Accepted, Refused, and Conflicted.
    NotCovered is the only non-definitive variant -- it means no evidence
    exists and therefore no citation is possible.
    """
    return isinstance(verdict, (Accepted, Refused, Conflicted))


def citations_of(verdict: ItemVerdict) -> tuple[Citation, ...]:
    """Return the verdict's citations, or () for NotCovered."""
    match verdict:
        case Accepted() | Refused() | Conflicted():
            return verdict.citations
        case NotCovered():
            return ()
        case _ as unreachable:  # pyright: ignore[reportUnnecessaryComparison]
            assert_never(unreachable)
