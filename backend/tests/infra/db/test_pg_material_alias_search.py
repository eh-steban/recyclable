# pyright: reportUnusedCallResult=false
# pyright: reportUnusedFunction=false
# pyright: reportAny=false
"""Postgres integration tests for PgMaterialAliasSearch.

Requires a live Postgres with the pg_trgm extension and migration 0004
applied. Skipped when the database is unreachable (via the `db_url`
fixture in conftest.py).

These tests verify that PgMaterialAliasSearch correctly:
  - Returns per-material MAX(similarity) ordered descending.
  - Excludes materials with similarity == 0 (HAVING MAX > 0).
  - Collapses multiple aliases for the same material to their max score.
  - Returns an empty list when no aliases match.
"""

import uuid
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from src.domain.knowledge_base.material import MaterialCategory, MaterialId
from src.infra.db.models.material_alias import MaterialAliasORM
from src.infra.db.repos.material_alias_search import PgMaterialAliasSearch

# SQL strings extracted to avoid implicit-string-concatenation warnings.
_SQL_INSERT_MATERIAL = (
    "INSERT INTO materials (id, canonical_name, slug, category)"
    " VALUES (:id, :name, :slug, :cat)"
)
_SQL_INSERT_ALIAS = (
    "INSERT INTO material_aliases (id, material_id, alias, weight)"
    " VALUES (:id, :mid, :alias, :weight)"
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_session(db_url: str) -> Generator[Session]:
    """Synchronous Session connected to the integration test database."""
    engine = create_engine(db_url)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture(autouse=True)
def _cleanup(db_session: Session) -> Generator[None]:
    """Delete rows inserted by each test after it runs."""
    yield
    db_session.execute(text("DELETE FROM material_aliases WHERE TRUE"))
    db_session.execute(text("DELETE FROM materials WHERE TRUE"))
    db_session.commit()


def _insert_material(
    session: Session,
    name: str,
) -> MaterialId:
    mat_id = uuid.uuid4()
    slug = name.lower().replace(" ", "-")
    session.execute(
        text(_SQL_INSERT_MATERIAL),
        {
            "id": mat_id,
            "name": name,
            "slug": slug,
            "cat": MaterialCategory.OTHER.value,
        },
    )
    session.commit()
    return MaterialId(mat_id)


def _insert_alias(
    session: Session,
    material_id: MaterialId,
    alias: str,
    weight: float = 1.0,
) -> None:
    session.execute(
        text(_SQL_INSERT_ALIAS),
        {
            "id": uuid.uuid4(),
            "mid": material_id.value,
            "alias": alias,
            "weight": weight,
        },
    )
    session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_search_returns_ordered_by_similarity_desc(
    db_session: Session,
) -> None:
    """Results are ordered by max_sim descending."""
    mat_a = _insert_material(db_session, "Cardboard")
    mat_b = _insert_material(db_session, "Carpet")
    _insert_alias(db_session, mat_a, "cardboard")
    _insert_alias(db_session, mat_b, "carpet")

    adapter = PgMaterialAliasSearch(db_session)
    results = adapter.search("cardboard")

    assert len(results) >= 1
    sims = [sim for _, sim in results]
    assert sims == sorted(sims, reverse=True)


@pytest.mark.integration
def test_search_excludes_zero_similarity(
    db_session: Session,
) -> None:
    """Materials whose alias has zero pg_trgm similarity are excluded."""
    mat_a = _insert_material(db_session, "Cardboard")
    _insert_alias(db_session, mat_a, "cardboard")

    adapter = PgMaterialAliasSearch(db_session)
    # "zzzzzzzqqqqq" has zero trigram overlap with "cardboard"
    results = adapter.search("zzzzzzzqqqqq")

    result_ids = {mid for mid, _ in results}
    assert mat_a not in result_ids


@pytest.mark.integration
def test_search_collapses_multi_alias_to_max(
    db_session: Session,
) -> None:
    """Multiple aliases for one material -> one row, using MAX sim.

    Uses aliases with deliberately different trigram distances to
    "cardboard" so MAX vs MIN is distinguishable:
      - "cardboard" is a near-exact match (high similarity)
      - "xyz"       has near-zero similarity

    The returned score must equal the MAX alias similarity, not the MIN.
    """
    mat_a = _insert_material(db_session, "Cardboard")
    # High-similarity alias
    _insert_alias(db_session, mat_a, "cardboard")
    # Low-similarity alias -- "xyz" has near-zero trigram overlap
    _insert_alias(db_session, mat_a, "xyz")

    adapter = PgMaterialAliasSearch(db_session)
    results = adapter.search("cardboard")

    mat_a_rows = [(mid, sim) for mid, sim in results if mid == mat_a]
    # Exactly one row for mat_a (collapsed)
    assert len(mat_a_rows) == 1
    _, reported_sim = mat_a_rows[0]

    # The reported similarity must be the MAX of the two aliases.
    # Calculate individual alias similarities for comparison.
    alias_sims_stmt = select(
        MaterialAliasORM.alias,
        func.similarity(MaterialAliasORM.alias, "cardboard").label("sim"),
    ).where(MaterialAliasORM.material_id == mat_a.value)
    alias_rows = db_session.execute(alias_sims_stmt).all()
    max_alias_sim = max(float(row[1]) for row in alias_rows)
    min_alias_sim = min(float(row[1]) for row in alias_rows)

    # MAX and MIN must differ so the test is meaningful
    assert max_alias_sim > min_alias_sim, (
        "alias similarities are indistinguishable -- test is vacuous"
    )
    # Reported score equals MAX
    assert abs(reported_sim - max_alias_sim) < 1e-6


@pytest.mark.integration
def test_search_empty_when_no_aliases(
    db_session: Session,
) -> None:
    """No aliases in DB -> empty results."""
    adapter = PgMaterialAliasSearch(db_session)
    results = adapter.search("cardboard")
    assert results == []


@pytest.mark.integration
def test_search_returns_material_ids_as_typed(
    db_session: Session,
) -> None:
    """Results carry MaterialId typed values, not raw UUIDs."""
    mat_a = _insert_material(db_session, "Glass")
    _insert_alias(db_session, mat_a, "glass")

    adapter = PgMaterialAliasSearch(db_session)
    results = adapter.search("glass")

    assert len(results) >= 1
    for mid, sim in results:
        assert isinstance(mid, MaterialId)
        assert isinstance(sim, float)
