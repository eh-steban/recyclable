"""MaterialNormalizer domain service interface and LLM port.

Two-step normalization:
1. Alias lookup (pure, no I/O) -- queries material_aliases for closest
   ILIKE match. A unique hit returns Resolved.
2. Haiku fallback (via port) -- if alias lookup returns zero candidates,
   classifies the query text and maps the ranked output to the
   NormalizationResult sum (Resolved | Ambiguous | Uncertain) per the
   thresholds in spec § Material normalizer.

The NormalizationResult sum type lives in normalization_result.py
in this same module to keep the dependency direction acyclic
(retrieval/ imports from knowledge_base/ but not the reverse).
"""

from typing import Protocol

from src.domain.knowledge_base.material import MaterialId
from src.domain.knowledge_base.normalization_result import NormalizationResult

# ---------------------------------------------------------------------------
# Step 2 classifier thresholds (spec § Material normalizer)
# ---------------------------------------------------------------------------

#: Minimum top-candidate confidence for any non-Uncertain outcome.
CONFIDENCE_THRESHOLD = 0.5

#: Minimum gap between top and second candidate for a Resolved outcome.
#: Below this gap (but with top >= CONFIDENCE_THRESHOLD), the result is
#: Ambiguous and lists the close cluster.
CANDIDATE_GAP_THRESHOLD = 0.2


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
    ) -> list[tuple[MaterialId, float]]:
        """Classify query_text against known material slugs.

        Returns ranked (material_id, confidence) pairs in descending
        confidence order. The MaterialNormalizer maps the ranked list
        to the NormalizationResult sum using the thresholds above.
        """
        ...


# ---------------------------------------------------------------------------
# MaterialNormalizer domain service interface
# ---------------------------------------------------------------------------


class MaterialNormalizer(Protocol):
    """Domain service interface for material normalization.

    Returns one of the three NormalizationResult variants:
    Resolved | Ambiguous | Uncertain. Implementations must always
    produce a variant; there is no None return.
    """

    def normalize(self, query_text: str) -> NormalizationResult: ...
