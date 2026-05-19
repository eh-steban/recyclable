# pyright: reportAny=false
# reportAny disabled here: SQLAlchemy Row results from .all() are typed as
# Any at runtime. The explicit float() cast makes the conversion safe;
# suppressing the warning is consistent with the pattern in
# infra/db/repos/answer_audit_record_repo.py.
"""PgMaterialAliasSearch -- pg_trgm similarity query adapter.

Implements the MaterialAliasSearch port from
src/domain/knowledge_base/material_normalizer.py.

Runs the per-material max trigram similarity query against
material_aliases using the pg_trgm similarity() function.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.domain.knowledge_base.material import MaterialId
from src.infra.db.models.material_alias import MaterialAliasORM

logger = logging.getLogger(__name__)


class PgMaterialAliasSearch:
    """Postgres-backed MaterialAliasSearch: pg_trgm similarity query.

    Groups aliases by material_id and returns MAX(similarity) per
    material, ordered descending. Returns only materials with
    similarity > 0.

    The weight column in material_aliases is intentionally ignored --
    this adapter reads only alias text and the similarity score.
    """

    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    def search(self, query_text: str) -> list[tuple[MaterialId, float]]:
        """Return per-material MAX(similarity) tuples, ordered descending.

        Requires pg_trgm extension (migration 0004).
        """
        logger.debug("PgMaterialAliasSearch.search: query=%r", query_text)
        # similarity() is a pg_trgm function; SQLAlchemy's func wrapper
        # delegates to the database which requires the extension loaded.
        sim_col = func.similarity(MaterialAliasORM.alias, query_text)
        max_sim = func.max(sim_col).label("max_sim")
        stmt = (
            select(
                MaterialAliasORM.material_id,
                max_sim,
            )
            .group_by(MaterialAliasORM.material_id)
            .having(func.max(sim_col) > 0)
            .order_by(max_sim.desc())
        )
        rows = self._session.execute(stmt).all()
        # Row is (material_id: uuid.UUID, max_sim: Decimal|float).
        return [(MaterialId(row[0]), float(row[1])) for row in rows]
