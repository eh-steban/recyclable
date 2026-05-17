"""Concrete MaterialNormalizer: alias lookup + Haiku LLM fallback.

Implements the MaterialNormalizer Protocol from
domain/knowledge_base/material_normalizer.py.

Step 1: query material_aliases ILIKE match against query_text.
  - Unique match -> Resolved.
  - Multiple close matches -> Ambiguous.
  - Zero matches -> Step 2.

Step 2 (LLM fallback): call MaterialNormalizerLLM.classify() and apply
the confidence thresholds from the Protocol module.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.domain.knowledge_base.material import Material, MaterialId
from src.domain.knowledge_base.material_normalizer import (
    CANDIDATE_GAP_THRESHOLD,
    CONFIDENCE_THRESHOLD,
    MaterialNormalizerLLM,
)
from src.domain.knowledge_base.normalization_result import (
    Ambiguous,
    NormalizationResult,
    Resolved,
    Uncertain,
)
from src.infra.db.models.material import MaterialORM
from src.infra.db.models.material_alias import MaterialAliasORM

logger = logging.getLogger(__name__)


class SqlMaterialNormalizer:
    """Database-backed MaterialNormalizer with LLM fallback.

    Alias lookup is case-insensitive (ILIKE). Haiku classify() is the
    fallback when no alias matches.
    """

    def __init__(
        self,
        session: Session,
        llm: MaterialNormalizerLLM,
    ) -> None:
        self._session = session
        self._llm = llm

    def normalize(self, query_text: str) -> NormalizationResult:
        """Return Resolved | Ambiguous | Uncertain for query_text."""
        # Step 1: alias lookup (case-insensitive exact match on alias text).
        result = self._alias_lookup(query_text)
        if result is not None:
            return result

        # Step 2: LLM fallback via Haiku.
        known_ids = self._all_material_ids()
        ranked = self._llm.classify(query_text, known_ids)
        return self._classify_to_result(ranked)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_material(self, material_id: MaterialId) -> Material | None:
        row = self._session.get(MaterialORM, material_id.value)
        if row is None:
            return None
        return self._to_domain(row)

    def _alias_lookup(self, query_text: str) -> NormalizationResult | None:
        """ILIKE lookup against material_aliases.alias.

        Returns Resolved on unique match, Ambiguous on close cluster,
        None when no match found.
        """
        stmt = (
            select(MaterialAliasORM)
            .where(
                func.lower(MaterialAliasORM.alias)
                == func.lower(query_text.strip())
            )
            .order_by(MaterialAliasORM.weight.desc())
        )
        rows = self._session.execute(stmt).scalars().all()
        if not rows:
            return None

        # Load the top match.
        top_material = self._load_material(MaterialId(rows[0].material_id))
        if top_material is None:
            return None

        if len(rows) == 1:
            return Resolved(material=top_material)

        # Multiple matches -- check if top weight clearly dominates.
        top_w = float(rows[0].weight)
        second_w = float(rows[1].weight)
        gap = top_w - second_w
        gap_threshold = CANDIDATE_GAP_THRESHOLD * top_w if top_w else 0
        if gap >= gap_threshold:
            return Resolved(material=top_material)

        # Close cluster -- load up to 5 candidate materials.
        candidates: list[Material] = []
        for row in rows[:5]:
            m = self._load_material(MaterialId(row.material_id))
            if m is not None:
                candidates.append(m)

        if len(candidates) >= 2:  # noqa: PLR2004
            return Ambiguous(candidates=tuple(candidates))

        # Fell through to single candidate after loading.
        return Resolved(material=candidates[0]) if candidates else None

    def _all_material_ids(self) -> list[MaterialId]:
        """Return all known MaterialIds for the LLM classify call."""
        stmt = select(MaterialORM.id)
        rows = self._session.execute(stmt).scalars().all()
        return [MaterialId(r) for r in rows]

    def _classify_to_result(
        self,
        ranked: list[tuple[MaterialId, float]],
    ) -> NormalizationResult:
        """Apply confidence thresholds to ranked (material_id, confidence)."""
        if not ranked:
            return Uncertain()

        top_id, top_conf = ranked[0]
        if top_conf < CONFIDENCE_THRESHOLD:
            return Uncertain()

        # Load the top material.
        top_material = self._load_material(top_id)
        if top_material is None:
            return Uncertain()

        if len(ranked) < 2:  # noqa: PLR2004
            return Resolved(material=top_material)

        _, second_conf = ranked[1]
        gap = top_conf - second_conf
        if gap >= CANDIDATE_GAP_THRESHOLD:
            return Resolved(material=top_material)

        # Close cluster -- load candidates above threshold.
        candidate_materials: list[Material] = []
        for mid, conf in ranked:
            if conf < CONFIDENCE_THRESHOLD:
                break
            m = self._load_material(mid)
            if m is not None:
                candidate_materials.append(m)
            if len(candidate_materials) >= 5:  # noqa: PLR2004
                break

        if len(candidate_materials) >= 2:  # noqa: PLR2004
            return Ambiguous(candidates=tuple(candidate_materials))

        return Resolved(material=top_material)

    @staticmethod
    def _to_domain(row: MaterialORM) -> Material:
        from src.domain.knowledge_base.material import MaterialCategory  # noqa: PLC0415, I001 -- deferred to avoid circular import

        return Material(
            id=MaterialId(row.id),
            canonical_name=row.canonical_name,
            slug=row.slug,
            category=MaterialCategory(row.category),
        )
