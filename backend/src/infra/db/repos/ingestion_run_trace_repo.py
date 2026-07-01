"""Postgres implementation of the IngestionRunTraceRepo port."""

# pyright: reportAny=false, reportExplicitAny=false

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.domain.ingestion.ingestion_run_trace import (
    IngestionRunTrace,
    IngestionRunTraceId,
)
from src.infra.db.models.ingestion_run_trace import IngestionRunTraceORM
from src.infra.db.repos._exceptions import translate_repo_exceptions

logger = logging.getLogger(__name__)


class PgIngestionRunTraceRepo:
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    def next_identity(self) -> IngestionRunTraceId:
        return IngestionRunTraceId(uuid.uuid4())

    def save(self, trace: IngestionRunTrace) -> None:
        logger.debug("saving ingestion_run_trace id=%s", trace.id)
        stmt = (
            insert(IngestionRunTraceORM)
            .values(
                id=trace.id.value,
                seed_url=trace.seed_url,
                created_at=trace.created_at,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={"seed_url": trace.seed_url},
            )
        )
        with translate_repo_exceptions("IngestionRunTrace", str(trace.id)):
            _ = self._session.execute(stmt)

    def find_by_id(
        self, trace_id: IngestionRunTraceId
    ) -> IngestionRunTrace | None:
        stmt = select(IngestionRunTraceORM).where(
            IngestionRunTraceORM.id == trace_id.value
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return _to_domain(row)


def _to_domain(row: IngestionRunTraceORM) -> IngestionRunTrace:
    return IngestionRunTrace(
        id=IngestionRunTraceId(row.id),
        seed_url=row.seed_url,
        created_at=row.created_at,
    )
