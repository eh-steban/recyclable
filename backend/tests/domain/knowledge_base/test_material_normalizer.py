"""Domain-service tests for MaterialNormalizerService.

Pure tests: MemMaterialAliasSearch + FakeMaterialNormalizerLLM +
MemMaterialRepo. No mocks, no MagicMock, no SQLAlchemy Session.

Covers every resolution branch:
  - Trigram resolve (single + clear gap)
  - Trigram ambiguous (close cluster, cap=5)
  - Multi-alias same-material max-collapse (contract documented on port)
  - Fall-through to LLM
  - LLM resolve / ambiguous / uncertain
  - Orphaned alias -> Uncertain + ERROR log
  - Boundary-equality cases (value exactly at threshold, at gap)
    for both trigram and LLM models
  - Fewer-than-2-loadable fall-throughs
  - LLM classify called with full material ID set
"""

import logging
import uuid
from typing import final

import pytest

from src.domain.knowledge_base.material import (
    Material,
    MaterialCategory,
    MaterialId,
)
from src.domain.knowledge_base.material_normalizer import (
    LLM_CONFIDENCE_GAP,
    LLM_CONFIDENCE_THRESHOLD,
    TRIGRAM_SIMILARITY_GAP,
    TRIGRAM_SIMILARITY_THRESHOLD,
    MaterialNormalizerService,
)
from src.domain.knowledge_base.normalization_result import (
    Ambiguous,
    Resolved,
    Uncertain,
)
from tests._fakes.material_alias_search import MemMaterialAliasSearch
from tests._fakes.material_repo import MemMaterialRepo

# ---------------------------------------------------------------------------
# Shared material IDs
# ---------------------------------------------------------------------------

_MAT_A_ID = MaterialId(uuid.uuid4())
_MAT_B_ID = MaterialId(uuid.uuid4())
_MAT_C_ID = MaterialId(uuid.uuid4())


# ---------------------------------------------------------------------------
# Fake LLM port
# ---------------------------------------------------------------------------


@final
class FakeMaterialNormalizerLLM:
    """Pre-set ranked list returned from classify().

    Constructing with a preset `result` list simulates Haiku returning
    ranked (material_id, confidence) pairs. The call is recorded so tests
    can assert it was/wasn't called.
    """

    def __init__(
        self, result: list[tuple[MaterialId, float]] | None = None
    ) -> None:
        self._result: list[tuple[MaterialId, float]] = result or []
        self.call_count = 0
        self.last_query: str | None = None
        self.last_known_materials: list[Material] | None = None

    def classify(
        self,
        query_text: str,
        known_materials: list[Material],
    ) -> list[tuple[MaterialId, float]]:
        self.call_count += 1
        self.last_query = query_text
        self.last_known_materials = list(known_materials)
        return list(self._result)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mat(material_id: MaterialId, name: str = "Test") -> Material:
    return Material(
        id=material_id,
        canonical_name=name,
        slug=name.lower().replace(" ", "-"),
        category=MaterialCategory.OTHER,
    )


def _never_called_llm() -> FakeMaterialNormalizerLLM:
    """LLM that asserts it is never called (for trigram-resolved tests)."""
    return FakeMaterialNormalizerLLM(result=[])


def _build_service(
    rows: list[tuple[MaterialId, float]],
    materials: list[Material],
    llm: FakeMaterialNormalizerLLM | None = None,
) -> tuple[MaterialNormalizerService, FakeMaterialNormalizerLLM]:
    """Assemble a MaterialNormalizerService with in-memory ports."""
    _llm = llm or _never_called_llm()
    alias_search = MemMaterialAliasSearch(rows)
    repo = MemMaterialRepo()
    for mat in materials:
        repo.save(mat)
    svc = MaterialNormalizerService(
        alias_search=alias_search,
        llm=_llm,
        material_lookup=repo,
    )
    return svc, _llm


# ===========================================================================
# Trigram -- Resolved
# ===========================================================================


class TestTrigramResolved:
    """Step 1 resolves when top_sim >= threshold AND gap >= TRIGRAM_SIM_GAP."""

    def test_trigram_resolve_single_row(self) -> None:
        """Single alias row above threshold returns Resolved."""
        mat_a = _mat(_MAT_A_ID, "Cardboard")
        svc, llm = _build_service(
            rows=[(_MAT_A_ID, 0.85)],
            materials=[mat_a],
        )

        result = svc.normalize("cardboard")

        assert isinstance(result, Resolved)
        assert result.material == mat_a
        assert llm.call_count == 0

    def test_trigram_resolve_clear_gap_over_second(self) -> None:
        """Two distinct materials: top dominates by >= the gap."""
        mat_a = _mat(_MAT_A_ID, "Cardboard")
        mat_b = _mat(_MAT_B_ID, "Carpet")
        # gap = 0.85 - 0.65 = 0.20 >= TRIGRAM_SIMILARITY_GAP (0.15)
        svc, llm = _build_service(
            rows=[(_MAT_A_ID, 0.85), (_MAT_B_ID, 0.65)],
            materials=[mat_a, mat_b],
        )

        result = svc.normalize("cardboard")

        assert isinstance(result, Resolved)
        assert result.material == mat_a
        assert llm.call_count == 0

    def test_trigram_resolve_gap_exactly_at_threshold(self) -> None:
        """Gap exactly equal to TRIGRAM_SIMILARITY_GAP resolves (inclusive)."""
        mat_a = _mat(_MAT_A_ID, "Glass")
        mat_b = _mat(_MAT_B_ID, "Grass")
        top_sim = TRIGRAM_SIMILARITY_THRESHOLD + 0.1
        second_sim = top_sim - TRIGRAM_SIMILARITY_GAP  # gap == exactly
        svc, _ = _build_service(
            rows=[(_MAT_A_ID, top_sim), (_MAT_B_ID, second_sim)],
            materials=[mat_a, mat_b],
        )

        result = svc.normalize("glass")

        assert isinstance(result, Resolved)
        assert result.material == mat_a

    def test_trigram_sim_exactly_at_threshold_gap_sufficient(self) -> None:
        """top_sim == TRIGRAM_SIMILARITY_THRESHOLD (boundary inclusive)."""
        mat_a = _mat(_MAT_A_ID, "Plastic")
        mat_b = _mat(_MAT_B_ID, "Elastic")
        top_sim = TRIGRAM_SIMILARITY_THRESHOLD  # exactly at threshold
        second_sim = 0.0  # gap is huge
        svc, _ = _build_service(
            rows=[(_MAT_A_ID, top_sim), (_MAT_B_ID, second_sim)],
            materials=[mat_a, mat_b],
        )

        result = svc.normalize("plastic")

        assert isinstance(result, Resolved)


# ===========================================================================
# Trigram -- Ambiguous
# ===========================================================================


class TestTrigramAmbiguous:
    """Step 1 -> Ambiguous when top >= threshold but gap < TRIGRAM_SIM_GAP."""

    def test_trigram_ambiguous_tight_cluster(self) -> None:
        """Two materials above threshold, gap < TRIGRAM_SIMILARITY_GAP."""
        mat_a = _mat(_MAT_A_ID, "Glass")
        mat_b = _mat(_MAT_B_ID, "Gloss")
        # gap = 0.72 - 0.65 = 0.07 < TRIGRAM_SIMILARITY_GAP (0.15)
        svc, _ = _build_service(
            rows=[(_MAT_A_ID, 0.72), (_MAT_B_ID, 0.65)],
            materials=[mat_a, mat_b],
        )

        result = svc.normalize("glas")

        assert isinstance(result, Ambiguous)
        assert mat_a in result.candidates
        assert mat_b in result.candidates

    def test_trigram_ambiguous_gap_just_below_threshold(self) -> None:
        """Gap is (TRIGRAM_SIMILARITY_GAP - epsilon) -> Ambiguous."""
        mat_a = _mat(_MAT_A_ID, "Paper")
        mat_b = _mat(_MAT_B_ID, "Paver")
        top_sim = 0.80
        second_sim = top_sim - (TRIGRAM_SIMILARITY_GAP - 0.01)
        svc, _ = _build_service(
            rows=[(_MAT_A_ID, top_sim), (_MAT_B_ID, second_sim)],
            materials=[mat_a, mat_b],
        )

        result = svc.normalize("paper")

        assert isinstance(result, Ambiguous)

    def test_trigram_ambiguous_caps_candidates_at_five(self) -> None:
        """Ambiguous result caps returned candidates at 5."""
        mat_ids = [MaterialId(uuid.uuid4()) for _ in range(7)]
        materials = [_mat(mid, f"Material{i}") for i, mid in enumerate(mat_ids)]
        # All above threshold, all close together (gap < TRIGRAM_SIMILARITY_GAP)
        rows = [(mid, 0.70 - i * 0.01) for i, mid in enumerate(mat_ids)]

        svc, _ = _build_service(rows=rows, materials=materials)

        result = svc.normalize("material")

        assert isinstance(result, Ambiguous)
        assert len(result.candidates) <= 5


# ===========================================================================
# Trigram -- Fall-through to LLM
# ===========================================================================


class TestTrigramFallThrough:
    """Step 1 falls through to Step 2 when top_sim < TRIGRAM_THRESHOLD."""

    def test_trigram_fallthrough_no_rows(self) -> None:
        """Zero similarity rows falls through to Step 2."""
        llm = FakeMaterialNormalizerLLM(result=[])
        svc, _ = _build_service(rows=[], materials=[], llm=llm)

        result = svc.normalize("xyzunknown")

        assert llm.call_count == 1
        assert isinstance(result, Uncertain)

    def test_trigram_fallthrough_low_similarity(self) -> None:
        """top_sim just below TRIGRAM_SIMILARITY_THRESHOLD falls through."""
        mat_a = _mat(_MAT_A_ID, "Foil")
        top_sim = TRIGRAM_SIMILARITY_THRESHOLD - 0.01  # just below
        # LLM returns a confident single result
        llm = FakeMaterialNormalizerLLM(result=[(_MAT_A_ID, 0.9)])
        svc, _ = _build_service(
            rows=[(_MAT_A_ID, top_sim)],
            materials=[mat_a],
            llm=llm,
        )

        result = svc.normalize("foi")

        assert llm.call_count == 1
        assert isinstance(result, Resolved)
        assert result.material.id == _MAT_A_ID

    def test_trigram_threshold_boundary_just_below_falls_through(
        self,
    ) -> None:
        """top_sim exactly at (TRIGRAM_SIMILARITY_THRESHOLD - epsilon)."""
        top_sim = TRIGRAM_SIMILARITY_THRESHOLD - 0.001
        llm = FakeMaterialNormalizerLLM(result=[])
        svc, _ = _build_service(
            rows=[(_MAT_A_ID, top_sim)],
            materials=[],
            llm=llm,
        )

        result = svc.normalize("met")

        assert llm.call_count == 1
        assert isinstance(result, Uncertain)


# ===========================================================================
# Multi-alias same-material max-collapse (contract test)
# ===========================================================================


class TestMultiAliasSameMaterialCollapse:
    """Multiple aliases for the same material: only max sim is used.

    The SQL query (PgMaterialAliasSearch) groups by material_id and
    takes MAX(similarity). The domain service relies on this -- the
    MemMaterialAliasSearch receives pre-collapsed rows. These tests
    verify the domain service's behavior given correctly-collapsed input
    (the contract documented on MaterialAliasSearch.search()).
    """

    def test_same_material_max_used_resolves(self) -> None:
        """Pre-collapsed rows: mat_a wins 0.90, mat_b at 0.75.
        Gap=0.15 >= TRIGRAM_SIMILARITY_GAP -> Resolved."""
        mat_a = _mat(_MAT_A_ID, "Cardboard")
        mat_b = _mat(_MAT_B_ID, "CardBox")
        # Already collapsed: max alias similarity for mat_a is 0.90
        svc, _ = _build_service(
            rows=[(_MAT_A_ID, 0.90), (_MAT_B_ID, 0.75)],
            materials=[mat_a, mat_b],
        )

        result = svc.normalize("cardboard")

        # Gap = 0.15 which is exactly at TRIGRAM_SIMILARITY_GAP -> Resolved
        assert isinstance(result, Resolved)
        assert result.material == mat_a

    def test_single_material_no_false_ambiguity(self) -> None:
        """Without collapse, two aliases for same material would look
        ambiguous. With collapse, only one row per material_id appears."""
        mat_a = _mat(_MAT_A_ID, "Plastic")
        # Already collapsed: one row for mat_a
        svc, _ = _build_service(
            rows=[(_MAT_A_ID, 0.88)],
            materials=[mat_a],
        )

        result = svc.normalize("plastic")

        assert isinstance(result, Resolved)
        assert result.material == mat_a


# ===========================================================================
# Trigram -- Orphaned alias
# ===========================================================================


class TestTrigramOrphanedAlias:
    """Trigram gap-sufficient: Uncertain when material lookup returns None."""

    def test_orphaned_alias_gap_sufficient_returns_uncertain(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """top material with gap >= TRIGRAM_SIMILARITY_GAP but
        find_by_id returns None (orphaned alias row) -> Uncertain + ERROR."""
        orphan_id = MaterialId(uuid.uuid4())
        # material_id has an alias row but no material row in the repo
        svc, _ = _build_service(
            rows=[(orphan_id, 0.85)],
            materials=[],  # no material row for orphan_id
        )

        with caplog.at_level(logging.ERROR):
            result = svc.normalize("cardboard")

        assert isinstance(result, Uncertain)
        # ERROR log must surface the orphaned alias
        assert any(
            "orphaned alias" in r.message.lower()
            for r in caplog.records
            if r.levelno == logging.ERROR
        )


# ===========================================================================
# Trigram -- Ambiguous close-cluster with fewer than 2 loadable
# ===========================================================================


class TestTrigramAmbiguousFewerThanTwoLoadable:
    """Close-cluster falls back when fewer than 2 candidates load."""

    def test_exactly_one_loadable_returns_resolved(self) -> None:
        """Close cluster (gap < TRIGRAM_SIMILARITY_GAP) with exactly 1
        loadable candidate -> Resolved(candidates[0])."""
        mat_a = _mat(_MAT_A_ID, "Cardboard")
        orphan_id = MaterialId(uuid.uuid4())

        # Both above threshold, gap < TRIGRAM_SIMILARITY_GAP -> close cluster
        # Only mat_a has a material row; orphan_id does not
        svc, _ = _build_service(
            rows=[(_MAT_A_ID, 0.72), (orphan_id, 0.68)],
            materials=[mat_a],
        )

        result = svc.normalize("cardboard")

        assert isinstance(result, Resolved)
        assert result.material == mat_a

    def test_zero_loadable_returns_uncertain(self) -> None:
        """Close cluster (gap < TRIGRAM_SIMILARITY_GAP) with 0 loadable
        candidates -> Uncertain."""
        orphan_a = MaterialId(uuid.uuid4())
        orphan_b = MaterialId(uuid.uuid4())

        svc, _ = _build_service(
            rows=[(orphan_a, 0.72), (orphan_b, 0.68)],
            materials=[],  # neither alias has a material row
        )

        result = svc.normalize("cardboard")

        assert isinstance(result, Uncertain)

    def test_orphaned_alias_in_cluster_logs_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Close-cluster orphaned alias is logged at ERROR, matching the
        Resolved-path behavior (symmetric data-integrity surfacing)."""
        mat_a = _mat(_MAT_A_ID, "Cardboard")
        orphan_id = MaterialId(uuid.uuid4())

        svc, _ = _build_service(
            rows=[(_MAT_A_ID, 0.72), (orphan_id, 0.68)],
            materials=[mat_a],  # orphan_id has no material row
        )

        with caplog.at_level(logging.ERROR):
            svc.normalize("cardboard")

        assert any(
            "orphaned alias" in r.getMessage().lower()
            and str(orphan_id) in r.getMessage()
            for r in caplog.records
        )


# ===========================================================================
# LLM fallback -- Resolved
# ===========================================================================


class TestLLMResolved:
    """Step 2: Haiku returns top >= 0.5 with gap >= LLM_CONFIDENCE_GAP."""

    def test_llm_resolve_confident_single(self) -> None:
        """Single candidate above LLM_CONFIDENCE_THRESHOLD -> Resolved."""
        mat_a = _mat(_MAT_A_ID, "Glass")
        llm = FakeMaterialNormalizerLLM(result=[(_MAT_A_ID, 0.95)])
        svc, _ = _build_service(
            rows=[],  # Step 1 produces no rows
            materials=[mat_a],
            llm=llm,
        )

        result = svc.normalize("glass bottle")

        assert isinstance(result, Resolved)
        assert result.material == mat_a

    def test_llm_resolve_gap_exactly_at_threshold(self) -> None:
        """Gap == LLM_CONFIDENCE_GAP exactly -> Resolved (inclusive)."""
        mat_a = _mat(_MAT_A_ID, "Metal")
        mat_b = _mat(_MAT_B_ID, "Metal Can")
        top_conf = LLM_CONFIDENCE_THRESHOLD + 0.1
        second_conf = top_conf - LLM_CONFIDENCE_GAP  # gap == threshold exactly
        llm = FakeMaterialNormalizerLLM(
            result=[(_MAT_A_ID, top_conf), (_MAT_B_ID, second_conf)]
        )
        svc, _ = _build_service(
            rows=[],
            materials=[mat_a, mat_b],
            llm=llm,
        )

        result = svc.normalize("steel can")

        assert isinstance(result, Resolved)
        assert result.material == mat_a


# ===========================================================================
# LLM fallback -- Ambiguous
# ===========================================================================


class TestLLMAmbiguous:
    """Step 2: Haiku returns top >= 0.5 but gap < LLM_CONFIDENCE_GAP."""

    def test_llm_ambiguous_close_cluster(self) -> None:
        """Two candidates above threshold, gap < LLM_CONFIDENCE_GAP."""
        mat_a = _mat(_MAT_A_ID, "Glass")
        mat_b = _mat(_MAT_B_ID, "Glaze")
        # gap = 0.75 - 0.65 = 0.10 < LLM_CONFIDENCE_GAP (0.20)
        llm = FakeMaterialNormalizerLLM(
            result=[(_MAT_A_ID, 0.75), (_MAT_B_ID, 0.65)]
        )
        svc, _ = _build_service(
            rows=[],
            materials=[mat_a, mat_b],
            llm=llm,
        )

        result = svc.normalize("glas")

        assert isinstance(result, Ambiguous)
        assert mat_a in result.candidates
        assert mat_b in result.candidates

    def test_llm_ambiguous_gap_just_below_threshold(self) -> None:
        """Gap is LLM_CONFIDENCE_GAP - epsilon -> Ambiguous."""
        mat_a = _mat(_MAT_A_ID, "Cardboard")
        mat_b = _mat(_MAT_B_ID, "Cardstock")
        top_conf = 0.80
        second_conf = top_conf - (LLM_CONFIDENCE_GAP - 0.01)
        llm = FakeMaterialNormalizerLLM(
            result=[(_MAT_A_ID, top_conf), (_MAT_B_ID, second_conf)]
        )
        svc, _ = _build_service(
            rows=[],
            materials=[mat_a, mat_b],
            llm=llm,
        )

        result = svc.normalize("card")

        assert isinstance(result, Ambiguous)


# ===========================================================================
# LLM fallback -- Uncertain
# ===========================================================================


class TestLLMUncertain:
    """Step 2: Haiku returns top < LLM_CONFIDENCE_THRESHOLD -> Uncertain."""

    def test_llm_uncertain_empty_results(self) -> None:
        """LLM returns no candidates -> Uncertain."""
        llm = FakeMaterialNormalizerLLM(result=[])
        svc, _ = _build_service(rows=[], materials=[], llm=llm)

        result = svc.normalize("xyzzy")

        assert isinstance(result, Uncertain)

    def test_llm_uncertain_low_confidence(self) -> None:
        """LLM: top confidence < LLM_CONFIDENCE_THRESHOLD -> Uncertain."""
        llm = FakeMaterialNormalizerLLM(
            result=[(_MAT_A_ID, LLM_CONFIDENCE_THRESHOLD - 0.01)]
        )
        svc, _ = _build_service(rows=[], materials=[], llm=llm)

        result = svc.normalize("stuff")

        assert isinstance(result, Uncertain)

    def test_llm_uncertain_confidence_exactly_below_threshold(
        self,
    ) -> None:
        """top confidence == LLM_CONFIDENCE_THRESHOLD - epsilon -> Uncertain."""
        llm = FakeMaterialNormalizerLLM(
            result=[(_MAT_A_ID, LLM_CONFIDENCE_THRESHOLD - 0.001)]
        )
        svc, _ = _build_service(rows=[], materials=[], llm=llm)

        result = svc.normalize("thingy")

        assert isinstance(result, Uncertain)


# ===========================================================================
# LLM -- top load returns None -> Uncertain
# ===========================================================================


class TestLLMTopLoadNone:
    """Step 2: find_by_id returns None for top candidate -> Uncertain."""

    def test_llm_top_material_load_none_returns_uncertain(self) -> None:
        """LLM returns top above LLM_CONFIDENCE_THRESHOLD but find_by_id
        returns None for top_id -> Uncertain."""
        orphan_id = MaterialId(uuid.uuid4())
        llm = FakeMaterialNormalizerLLM(result=[(orphan_id, 0.95)])
        svc, _ = _build_service(
            rows=[],
            materials=[],  # no material row for orphan_id
            llm=llm,
        )

        result = svc.normalize("unknown material")

        assert isinstance(result, Uncertain)


# ===========================================================================
# LLM -- Ambiguous with fewer than 2 loadable candidates
# ===========================================================================


class TestLLMAmbiguousFewerThanTwoLoadable:
    """LLM Ambiguous branch falls back to Resolved(top) when <2 load."""

    def test_llm_ambiguous_one_loadable_returns_resolved_top(
        self,
    ) -> None:
        """LLM returns gap < LLM_CONFIDENCE_GAP but only top loads
        (second is orphaned) -> Resolved(top_material)."""
        mat_a = _mat(_MAT_A_ID, "Glass")
        orphan_id = MaterialId(uuid.uuid4())
        # gap < LLM_CONFIDENCE_GAP -> Ambiguous branch, but only 1 loads
        top_conf = 0.80
        second_conf = top_conf - (LLM_CONFIDENCE_GAP - 0.01)
        llm = FakeMaterialNormalizerLLM(
            result=[(_MAT_A_ID, top_conf), (orphan_id, second_conf)]
        )
        svc, _ = _build_service(
            rows=[],
            materials=[mat_a],  # orphan_id has no material row
            llm=llm,
        )

        result = svc.normalize("glass shard")

        assert isinstance(result, Resolved)
        assert result.material == mat_a


# ===========================================================================
# LLM -- top_conf exactly at LLM_CONFIDENCE_THRESHOLD (boundary inclusive)
# ===========================================================================


class TestLLMConfidenceThresholdBoundary:
    """top_conf == LLM_CONFIDENCE_THRESHOLD: not Uncertain; proceeds to gap."""

    def test_llm_confidence_exactly_at_threshold_not_uncertain(
        self,
    ) -> None:
        """top_conf == LLM_CONFIDENCE_THRESHOLD is >= threshold, so the
        Uncertain branch is NOT taken. With a single candidate and no
        second entry the gap path is skipped -- result is Resolved."""
        mat_a = _mat(_MAT_A_ID, "Paper")
        # Exactly at boundary -- strict < means this is NOT Uncertain.
        # Single candidate -> len(ranked) < 2 -> Resolved(top_material).
        llm = FakeMaterialNormalizerLLM(
            result=[(_MAT_A_ID, LLM_CONFIDENCE_THRESHOLD)]
        )
        svc, _ = _build_service(rows=[], materials=[mat_a], llm=llm)

        result = svc.normalize("paper")

        assert isinstance(result, Resolved)
        assert result.material == mat_a


# ===========================================================================
# LLM -- classify called with full material set
# ===========================================================================


class TestLLMClassifyCalledWithAllMaterials:
    """Step 2 calls llm.classify with the full set from all_materials()."""

    def test_llm_classify_receives_all_materials(self) -> None:
        """llm.classify is called with the full list returned by
        material_lookup.all_materials(), not a subset, including each
        material's canonical name."""
        mat_a = _mat(_MAT_A_ID, "Material A")
        mat_b = _mat(_MAT_B_ID, "Material B")
        mat_c = _mat(_MAT_C_ID, "Material C")
        llm = FakeMaterialNormalizerLLM(result=[])
        svc, _ = _build_service(
            rows=[],
            materials=[mat_a, mat_b, mat_c],
            llm=llm,
        )

        _ = svc.normalize("unknown query")

        assert llm.call_count == 1
        assert llm.last_known_materials is not None
        passed_values = {m.id.value for m in llm.last_known_materials}
        expected = {_MAT_A_ID.value, _MAT_B_ID.value, _MAT_C_ID.value}
        assert passed_values == expected
        assert {m.canonical_name for m in llm.last_known_materials} == {
            "Material A",
            "Material B",
            "Material C",
        }
