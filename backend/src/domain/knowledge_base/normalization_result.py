"""NormalizationResult sum type.

The output of `MaterialNormalizer.normalize()`. Three variants:

- `Resolved(material)` -- one confident match.
- `Ambiguous(candidates)` -- multiple close candidates; the input
  could plausibly refer to any of them.
- `Uncertain` -- no confident classification at all.

Lives in `knowledge_base/` with its producer (`MaterialNormalizer`)
rather than in `retrieval/` to keep the module dependency direction
acyclic: `retrieval/` already imports from `knowledge_base/`, so the
result type must not flow the other way.

See `private/specs/01-sonnet-user-path.md` § Material normalizer for
the threshold logic that maps Step 2's ranked candidates to the
sum variants.
"""

from dataclasses import dataclass, field

from src.domain.knowledge_base.material import Material


@dataclass(frozen=True, slots=True)
class Resolved:
    """One confident match."""

    material: Material


@dataclass(frozen=True, slots=True)
class Ambiguous:
    """Multiple close candidate materials.

    Raises ValueError if fewer than two candidates are supplied --
    Ambiguous by definition is plural.
    """

    candidates: tuple[Material, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        count = len(self.candidates)
        if count < 2:  # noqa: PLR2004
            raise ValueError(
                f"Ambiguous requires at least 2 candidates; got {count}"
            )


@dataclass(frozen=True, slots=True)
class Uncertain:
    """No confident classification.

    Constructed without parameters; equal to any other Uncertain
    instance by value.
    """


#: The NormalizationResult sum type.
NormalizationResult = Resolved | Ambiguous | Uncertain
