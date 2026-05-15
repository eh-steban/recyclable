"""ItemVerdict sum type and its variants.

The domain verdict produced by the LLM and validated by GroundingValidator.
The wire layer maps this sum to the four-valued short_answer string tag.

Verdict mapping (per contracts/answer.md):
- Accepted (no conditions) -> short_answer = 'yes'
- Accepted (conditions non-empty) -> short_answer = 'conditional'
- Refused -> short_answer = 'no'
- NotCovered -> short_answer = 'unknown', refusal_reason = 'no_evidence'
- Conflicted -> short_answer = 'unknown', refusal_reason = 'no_evidence'
"""

from dataclasses import dataclass, field
from typing import cast


@dataclass(frozen=True, slots=True)
class Accepted:
    """The material is accepted under the queried jurisdiction's rules.

    conditions is an ordered list of prerequisite requirements (e.g. "Empty
    and rinse"). When non-empty, the wire layer renders
    short_answer = 'conditional'.
    """

    conditions: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        # Runtime boundary guard. The declared type is the contract;
        # callers crossing the LLM/DB boundary can still pass the wrong
        # type at runtime. cast(object, ...) defeats type checker
        # narrowing so this stays a real check -- reject, never
        # silently coerce.
        if not isinstance(cast(object, self.conditions), tuple):
            kind = type(self.conditions).__name__
            raise TypeError(f"Accepted.conditions must be a tuple, got {kind}")


@dataclass(frozen=True, slots=True)
class Refused:
    """The material is definitively refused/rejected.

    The LLM has determined the rule denies this material. Citations are
    required by INV-PROD-001.
    """

    pass


@dataclass(frozen=True, slots=True)
class NotCovered:
    """No rule found for this (jurisdiction, material) tuple.

    Maps to short_answer = 'unknown'. No Anthropic call is made;
    the application service produces this without consulting the LLM.
    """

    pass


@dataclass(frozen=True, slots=True)
class Conflicted:
    """Multiple sources disagree on this rule.

    The retrieval service surfaces the conflict; the GroundingValidator
    downgrades confidence to 'low'. Citations are required (INV-PROD-001).
    """

    pass


#: The ItemVerdict sum type.
ItemVerdict = Accepted | Refused | NotCovered | Conflicted


def is_definitive(verdict: ItemVerdict) -> bool:
    """Return True when a verdict requires citations (INV-PROD-001).

    Definitive verdicts are Accepted, Refused, and Conflicted.
    NotCovered is the only non-definitive variant -- it means no evidence
    exists and therefore no citation is possible.
    """
    return isinstance(verdict, (Accepted, Refused, Conflicted))
