"""Repo for source documents."""

import logging

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.domain.knowledge_base.source import SourceDocument
from src.infra.db.models.source_document import SourceDocumentORM

logger = logging.getLogger(__name__)


class SqlSourceDocumentRepo:
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

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
        _ = self._session.execute(stmt)
