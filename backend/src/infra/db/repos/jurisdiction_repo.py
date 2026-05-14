"""SQL implementation of the JurisdictionRepo port."""

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from src.domain.exceptions import (
    DuplicateAggregateError,
    RepositoryConcurrencyError,
)
from src.domain.knowledge_base.jurisdiction import (
    Jurisdiction,
    JurisdictionId,
    JurisdictionType,
    SupportedStatus,
)
from src.infra.db.models.jurisdiction import JurisdictionORM

logger = logging.getLogger(__name__)


class SqlJurisdictionRepo:
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Port surface
    # ------------------------------------------------------------------

    def next_identity(self) -> JurisdictionId:
        """Mint a fresh JurisdictionId (application-generated UUID)."""
        return JurisdictionId(uuid.uuid4())

    def save(self, jurisdiction: Jurisdiction) -> None:
        logger.debug("saving jurisdiction slug=%s", jurisdiction.slug)
        stmt = (
            insert(JurisdictionORM)
            .values(
                id=jurisdiction.id.value,
                name=jurisdiction.name,
                slug=jurisdiction.slug,
                type=jurisdiction.type.value,
                country=jurisdiction.country,
                supported_status=jurisdiction.supported_status.value,
                created_at=jurisdiction.created_at,
                updated_at=jurisdiction.updated_at,
            )
            .on_conflict_do_update(
                index_elements=["slug"],
                set_={
                    "name": jurisdiction.name,
                    "type": jurisdiction.type.value,
                    "country": jurisdiction.country,
                    "supported_status": jurisdiction.supported_status.value,
                    # Only bump updated_at when content actually changed.
                    "updated_at": func.now(),
                },
                where=(
                    (JurisdictionORM.name != jurisdiction.name)
                    | (JurisdictionORM.type != jurisdiction.type.value)
                    | (JurisdictionORM.country != jurisdiction.country)
                    | (
                        JurisdictionORM.supported_status
                        != jurisdiction.supported_status.value
                    )
                ),
            )
        )
        try:
            _ = self._session.execute(stmt)
        except IntegrityError as exc:
            raise DuplicateAggregateError(
                "Jurisdiction", str(jurisdiction.id)
            ) from exc
        except OperationalError as exc:
            raise RepositoryConcurrencyError(str(exc)) from exc

    def find_by_id(
        self, jurisdiction_id: JurisdictionId
    ) -> Jurisdiction | None:
        logger.debug("find_by_id jurisdiction_id=%s", jurisdiction_id)
        row = self._session.get(JurisdictionORM, jurisdiction_id.value)
        if row is None:
            return None
        return self._to_domain(row)

    def find_by_slug(self, slug: str) -> Jurisdiction | None:
        logger.debug("find_by_slug slug=%s", slug)
        stmt = select(JurisdictionORM).where(JurisdictionORM.slug == slug)
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_domain(row: JurisdictionORM) -> Jurisdiction:
        return Jurisdiction(
            id=JurisdictionId(row.id),
            name=row.name,
            slug=row.slug,
            type=JurisdictionType(row.type),
            country=row.country,
            supported_status=SupportedStatus(row.supported_status),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
