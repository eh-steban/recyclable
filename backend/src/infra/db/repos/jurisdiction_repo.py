"""Repo for jurisdictions."""

import logging
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.cli.seed_schemas.jurisdiction import Jurisdiction
from src.infra.db.models.jurisdiction import JurisdictionORM

logger = logging.getLogger(__name__)


class JurisdictionRepo(Protocol):
    def upsert(self, jurisdiction: Jurisdiction) -> None: ...
    def get_by_slug(self, slug: str) -> JurisdictionORM | None: ...


class SqlJurisdictionRepo:
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, jurisdiction: Jurisdiction) -> None:
        logger.debug("upserting jurisdiction slug=%s", jurisdiction.slug)
        stmt = (
            insert(JurisdictionORM)
            .values(
                id=jurisdiction.id,
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
        _ = self._session.execute(stmt)

    def get_by_slug(self, slug: str) -> JurisdictionORM | None:
        return self._session.scalar(
            select(JurisdictionORM).where(JurisdictionORM.slug == slug)
        )
