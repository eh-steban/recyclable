"""MaterialNormalizer -- domain service interface, LLM port, and constants.

The NormalizationResult sum type lives in normalization_result.py in this
same module to keep the dependency direction acyclic (retrieval/ imports
from knowledge_base/ but not the reverse).

See private/specs/01-sonnet-user-path.md § Material normalizer for the
pipeline design.
"""

import logging
from typing import Protocol

from src.domain.knowledge_base.material import (
    Material,
    MaterialId,
)
from src.domain.knowledge_base.material_repo import MaterialRepo
from src.domain.knowledge_base.normalization_result import (
    Ambiguous,
    NormalizationResult,
    Resolved,
    Uncertain,
)

logger = logging.getLogger(__name__)

# Minimum pg_trgm similarity() for the top material to be trusted at all.
# Below this value pg similarity search falls through to the Haiku
# fallback.
TRIGRAM_SIMILARITY_THRESHOLD: float = 0.7
# Minimum margin the top material must lead the second-best distinct
# material by to be Resolved rather than Ambiguous.
TRIGRAM_SIMILARITY_GAP: float = 0.15

# ---------------------------------------------------------------------------
# Classifier thresholds (spec § Material normalizer)
# ---------------------------------------------------------------------------

#: Minimum top-candidate confidence for any non-Uncertain outcome.
LLM_CONFIDENCE_THRESHOLD = 0.5

#: Minimum gap between top and second candidate for a Resolved outcome.
#: Below this gap (but with top >= LLM_CONFIDENCE_THRESHOLD), the result is
#: Ambiguous and lists the close cluster.
LLM_CONFIDENCE_GAP = 0.2

# Maximum number of Ambiguous candidates to surface.
_AMBIGUOUS_CAP = 5


# ---------------------------------------------------------------------------
# MaterialAliasSearch port (trigram lookup)
# ---------------------------------------------------------------------------


class MaterialAliasSearch(Protocol):
    """Port for the pg_trgm alias similarity search.

    Contract:
    - Returns per-material MAX trigram similarity, ordered descending.
    - Only materials with similarity > 0 are included.
    - Multiple aliases for the same material are collapsed to their
      maximum similarity score (the GROUP BY material_id MAX(sim)
      operation). The resolution model relies on this: `second_sim`
      is the best similarity of the second-highest-scoring *distinct*
      material, not an alias row of the same material.
    - Results are ordered by max_sim descending.
    """

    def search(self, query_text: str) -> list[tuple[MaterialId, float]]: ...


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
        confidence order. The MaterialNormalizerService maps the ranked
        list to the NormalizationResult sum using the thresholds above.
        """
        ...


# ---------------------------------------------------------------------------
# MaterialNormalizer concrete domain service
# ---------------------------------------------------------------------------


class MaterialNormalizerService:
    """Concrete domain service: two-step trigram + Haiku normalization.

    Pure domain service -- no SQLAlchemy, no Anthropic SDK. All I/O via
    the injected ports (MaterialAliasSearch, MaterialNormalizerLLM,
    MaterialRepo).

    See private/specs/01-sonnet-user-path.md § Material normalizer for
    the full Step 1 / Step 2 resolution model.
    """

    _alias_search: MaterialAliasSearch
    _llm: MaterialNormalizerLLM
    _material_lookup: MaterialRepo

    def __init__(
        self,
        alias_search: MaterialAliasSearch,
        llm: MaterialNormalizerLLM,
        material_lookup: MaterialRepo,
    ) -> None:
        self._alias_search = alias_search
        self._llm = llm
        self._material_lookup = material_lookup

    def normalize(self, query_text: str) -> NormalizationResult:
        """Return Resolved | Ambiguous | Uncertain for query_text."""
        logger.debug("MaterialNormalizer.normalize: query=%r", query_text)

        # Step 1: trigram similarity lookup.
        per_material_scores = self._alias_search.search(query_text)
        top_sim = per_material_scores[0][1] if per_material_scores else 0.0

        if top_sim >= TRIGRAM_SIMILARITY_THRESHOLD:
            result = self._resolve_trigram(per_material_scores)
            logger.debug(
                "MaterialNormalizer trigram result=%s top_sim=%.3f",
                type(result).__name__,
                top_sim,
            )
            return result

        # Step 2: Haiku LLM fallback.
        logger.debug(
            "MaterialNormalizer trigram miss top_sim=%.3f < %.3f, to Haiku",
            top_sim,
            TRIGRAM_SIMILARITY_THRESHOLD,
        )
        known_ids = self._material_lookup.all_material_ids()
        ranked = self._llm.classify(query_text, known_ids)
        result = self._resolve_llm(ranked)
        logger.debug("MaterialNormalizer llm result=%s", type(result).__name__)
        return result

    # ------------------------------------------------------------------
    # Text similarity resolution model
    # ------------------------------------------------------------------

    def _resolve_trigram(
        self,
        per_material_scores: list[tuple[MaterialId, float]],
    ) -> NormalizationResult:
        """Apply the trigram resolution model (spec § Material normalizer)."""
        top_mat_id, top_sim = per_material_scores[0]
        second_sim = (
            per_material_scores[1][1]
            if len(per_material_scores) >= 2  # noqa: PLR2004
            else 0.0
        )
        gap = top_sim - second_sim

        if gap >= TRIGRAM_SIMILARITY_GAP:
            # Clear winner -- load and return Resolved.
            top_material = self._material_lookup.find_by_id(top_mat_id)
            if top_material is not None:
                return Resolved(material=top_material)
            # Orphaned alias -- see the close-cluster path below for why
            # this is logged at ERROR.
            logger.error(
                "MaterialNormalizer trigram orphaned alias: "
                "material_id=%s has alias rows but no material row",  # pyright: ignore[reportImplicitStringConcatenation]
                top_mat_id,
            )
            return Uncertain()

        # Close cluster -- collect candidates up to the cap. An orphaned
        # alias (alias row with no matching material row) is a
        # data-integrity anomaly; log at ERROR on both resolution paths so
        # it surfaces in production monitoring.
        candidates: list[Material] = []
        for mat_id, _ in per_material_scores[:_AMBIGUOUS_CAP]:
            mat = self._material_lookup.find_by_id(mat_id)
            if mat is None:
                logger.error(
                    "MaterialNormalizer trigram orphaned alias: "
                    "material_id=%s has alias rows but no material row",  # pyright: ignore[reportImplicitStringConcatenation]
                    mat_id,
                )
                continue
            candidates.append(mat)

        if len(candidates) >= 2:  # noqa: PLR2004
            return Ambiguous(candidates=tuple(candidates))

        # Fell through to fewer than 2 loadable materials.
        return Resolved(material=candidates[0]) if candidates else Uncertain()

    # ------------------------------------------------------------------
    # LLM resolution model
    # ------------------------------------------------------------------

    def _resolve_llm(
        self,
        ranked: list[tuple[MaterialId, float]],
    ) -> NormalizationResult:
        """Apply the LLM confidence resolution model (spec § Material
        normalizer)."""
        if not ranked:
            return Uncertain()

        top_id, top_conf = ranked[0]
        if top_conf < LLM_CONFIDENCE_THRESHOLD:
            return Uncertain()

        # Load the top material.
        top_material = self._material_lookup.find_by_id(top_id)
        if top_material is None:
            return Uncertain()

        if len(ranked) < 2:  # noqa: PLR2004
            return Resolved(material=top_material)

        _, second_conf = ranked[1]
        gap = top_conf - second_conf
        if gap >= LLM_CONFIDENCE_GAP:
            return Resolved(material=top_material)

        # Close cluster -- load candidates above threshold.
        candidate_materials: list[Material] = []
        for mid, conf in ranked:
            if conf < LLM_CONFIDENCE_THRESHOLD:
                break
            mat = self._material_lookup.find_by_id(mid)
            if mat is not None:
                candidate_materials.append(mat)
            if len(candidate_materials) >= _AMBIGUOUS_CAP:
                break

        if len(candidate_materials) >= 2:  # noqa: PLR2004
            return Ambiguous(candidates=tuple(candidate_materials))

        return Resolved(material=top_material)


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
