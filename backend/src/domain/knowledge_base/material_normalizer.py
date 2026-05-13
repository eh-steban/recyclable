"""MaterialNormalizer domain service interface and LLM port.

Two-step normalization:
1. Alias lookup (pure, no I/O) -- queries material_aliases for closest
   ILIKE match. Returns the material with highest weight on tie.
2. Haiku fallback (via port) -- if alias lookup returns zero candidates,
   calls claude-haiku-4-5-20251001 with the material_normalize_v1 prompt.
   Returns the top candidate; sets ambiguous=True if confidence < 0.5.

The 0.5 threshold comes from the spec § Material normalizer:
"sets ambiguous = true if confidence < 0.5".
"""

from dataclasses import dataclass
from typing import Protocol

from src.domain.knowledge_base.material import Material, MaterialId

# ---------------------------------------------------------------------------
# Normalization result Value
# ---------------------------------------------------------------------------

#: Ambiguity threshold from spec § Material normalizer.
AMBIGUITY_THRESHOLD = 0.5


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    """Result of material normalization.

    Spec semantics: ambiguous=True when confidence < AMBIGUITY_THRESHOLD
    (0.5). When ambiguous, the RetrievalService refuses with a
    clarifying question rather than proceeding to answer composition.

    The field default is True (fail-safe). A normalizer implementation
    that returns a high-confidence result -- an alias-table hit, or a
    Haiku classification with confidence >= AMBIGUITY_THRESHOLD -- must
    set ambiguous=False explicitly. A forgetful implementer gets
    "ask for clarification" instead of a confidently wrong answer.
    """

    material: Material
    ambiguous: bool = True


# ---------------------------------------------------------------------------
# MaterialNormalizerLLM port (Haiku fallback)
# ---------------------------------------------------------------------------


class MaterialNormalizerLLM(Protocol):
    """Port for the Haiku-backed material classification fallback.

    Implemented in infra/external/anthropic_client.py.
    The domain never imports Anthropic SDK -- this Protocol is the seam.
    """

    def classify(
        self,
        query_text: str,
        known_material_ids: list[MaterialId],
    ) -> tuple[MaterialId, float]:
        """Classify query_text against known material slugs.

        Returns (top_material_id, confidence_score).
        A confidence score < AMBIGUITY_THRESHOLD means the result is
        ambiguous.
        """
        ...


# ---------------------------------------------------------------------------
# MaterialNormalizer domain service interface
# ---------------------------------------------------------------------------


class MaterialNormalizer(Protocol):
    """Domain service interface for material normalization.

    The default implementation tries alias lookup first; falls back to
    Haiku when alias lookup finds no candidates.
    """

    def normalize(self, query_text: str) -> NormalizationResult | None:
        """Normalize query_text to a Material.

        Returns None when no candidate can be found (not even via Haiku).
        Returns NormalizationResult with ambiguous=True when confidence is
        below AMBIGUITY_THRESHOLD.
        """
        ...
