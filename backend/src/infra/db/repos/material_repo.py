"""Repo for materials and aliases."""

import logging
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.domain.models.material import Material
from src.domain.models.material_alias import MaterialAlias
from src.infra.db.models.material import MaterialORM
from src.infra.db.models.material_alias import MaterialAliasORM

logger = logging.getLogger(__name__)


class MaterialRepo(Protocol):
    def upsert(self, material: Material) -> None: ...
    def upsert_alias(self, alias: MaterialAlias) -> None: ...
    def get_by_slug(self, slug: str) -> MaterialORM | None: ...


class SqlMaterialRepo:
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, material: Material) -> None:
        logger.debug("upserting material slug=%s", material.slug)
        stmt = (
            insert(MaterialORM)
            .values(
                id=material.id,
                canonical_name=material.canonical_name,
                slug=material.slug,
                category=material.category.value,
                parent_id=material.parent_id,
            )
            .on_conflict_do_update(
                index_elements=["slug"],
                set_={
                    "canonical_name": material.canonical_name,
                    "category": material.category.value,
                    "parent_id": material.parent_id,
                },
                # Only update when content actually changed.
                where=(
                    (MaterialORM.canonical_name != material.canonical_name)
                    | (MaterialORM.category != material.category.value)
                    | (
                        # parent_id nullable -- NULL IS DISTINCT FROM guard.
                        (MaterialORM.parent_id != material.parent_id)
                        if material.parent_id is not None
                        else (MaterialORM.parent_id.is_not(None))
                    )
                ),
            )
        )
        _ = self._session.execute(stmt)

    def upsert_alias(self, alias: MaterialAlias) -> None:
        logger.debug(
            "upserting alias material_id=%s alias=%s",
            alias.material_id,
            alias.alias,
        )
        stmt = (
            insert(MaterialAliasORM)
            .values(
                id=alias.id,
                material_id=alias.material_id,
                alias=alias.alias,
                weight=alias.weight,
            )
            .on_conflict_do_nothing(
                constraint="uq_material_aliases_material_id_alias",
            )
        )
        _ = self._session.execute(stmt)

    def get_by_slug(self, slug: str) -> MaterialORM | None:
        return self._session.scalar(
            select(MaterialORM).where(MaterialORM.slug == slug)
        )
