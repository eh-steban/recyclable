"""SQL implementation of the SourceRepo port."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from src.domain.exceptions import (
    DuplicateAggregateError,
    RepositoryConcurrencyError,
)
from src.domain.knowledge_base.jurisdiction import JurisdictionId
from src.domain.knowledge_base.source import SourceDocument, SourceId
from src.infra.db.models.source_document import SourceDocumentORM

logger = logging.getLogger(__name__)


class SqlSourceDocumentRepo:
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Port surface
    # ------------------------------------------------------------------

    def next_identity(self) -> SourceId:
        """Mint a fresh SourceId (application-generated UUID)."""
        return SourceId(uuid.uuid4())

    def save(self, doc: SourceDocument) -> None:
        logger.debug("saving source_document url=%s", doc.url)
        stmt = (
            insert(SourceDocumentORM)
            .values(
                id=doc.id.value,
                jurisdiction_id=doc.jurisdiction_id.value,
                url=doc.url,
                title=doc.title,
                authority_level=doc.authority_level,
                fetched_at=doc.fetched_at,
                effective_date=doc.effective_date,
                source_text=doc.source_text,
                source_text_hash=doc.source_text_hash,
                last_reviewed_at=doc.last_reviewed_at,
            )
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "url": doc.url,
                    "title": doc.title,
                    "authority_level": doc.authority_level,
                    "fetched_at": doc.fetched_at,
                    "effective_date": doc.effective_date,
                    "source_text": doc.source_text,
                    "source_text_hash": doc.source_text_hash,
                    "last_reviewed_at": doc.last_reviewed_at,
                },
                # Only update when content hash actually changed.
                where=(
                    SourceDocumentORM.source_text_hash != doc.source_text_hash
                ),
            )
        )
        try:
            _ = self._session.execute(stmt)
        except IntegrityError as exc:
            raise DuplicateAggregateError(
                "SourceDocument", str(doc.id)
            ) from exc
        except OperationalError as exc:
            raise RepositoryConcurrencyError(str(exc)) from exc

    def find_by_id(self, source_id: SourceId) -> SourceDocument | None:
        logger.debug("find_by_id source_id=%s", source_id)
        row = self._session.get(SourceDocumentORM, source_id.value)
        if row is None:
            return None
        return self._to_domain(row)

    def find_for_jurisdiction(
        self, jurisdiction_id: JurisdictionId
    ) -> list[SourceDocument]:
        logger.debug(
            "find_for_jurisdiction jurisdiction_id=%s", jurisdiction_id
        )
        stmt = select(SourceDocumentORM).where(
            SourceDocumentORM.jurisdiction_id == jurisdiction_id.value
        )
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_domain(row: SourceDocumentORM) -> SourceDocument:
        return SourceDocument(
            id=SourceId(row.id),
            jurisdiction_id=JurisdictionId(row.jurisdiction_id),
            url=row.url,
            title=row.title,
            authority_level=row.authority_level,
            fetched_at=row.fetched_at,
            source_text=row.source_text,
            source_text_hash=row.source_text_hash,
            effective_date=row.effective_date,
            last_reviewed_at=row.last_reviewed_at,
        )
