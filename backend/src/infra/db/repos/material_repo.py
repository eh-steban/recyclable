"""Postgres implementation of the MaterialRepo port."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.domain.knowledge_base.material import (
    Material,
    MaterialAlias,
    MaterialCategory,
    MaterialId,
)
from src.infra.db.models.material import MaterialORM
from src.infra.db.models.material_alias import MaterialAliasORM
from src.infra.db.repos._exceptions import translate_repo_exceptions

logger = logging.getLogger(__name__)


class PgMaterialRepo:
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Port surface
    # ------------------------------------------------------------------

    def next_identity(self) -> MaterialId:
        """Mint a fresh MaterialId (application-generated UUID)."""
        return MaterialId(uuid.uuid4())

    def save(self, material: Material) -> None:
        logger.debug("saving material slug=%s", material.slug)
        parent_uuid = (
            material.parent_id.value if material.parent_id is not None else None
        )
        stmt = (
            insert(MaterialORM)
            .values(
                id=material.id.value,
                canonical_name=material.canonical_name,
                slug=material.slug,
                category=material.category.value,
                parent_id=parent_uuid,
            )
            .on_conflict_do_update(
                index_elements=["slug"],
                set_={
                    "canonical_name": material.canonical_name,
                    "category": material.category.value,
                    "parent_id": parent_uuid,
                },
                # Only update when content actually changed.
                where=(
                    (MaterialORM.canonical_name != material.canonical_name)
                    | (MaterialORM.category != material.category.value)
                    | (
                        # parent_id nullable -- NULL IS DISTINCT FROM guard.
                        (MaterialORM.parent_id != parent_uuid)
                        if parent_uuid is not None
                        else (MaterialORM.parent_id.is_not(None))
                    )
                ),
            )
        )
        with translate_repo_exceptions("Material", str(material.id)):
            _ = self._session.execute(stmt)

    def save_alias(self, alias: MaterialAlias) -> None:
        logger.debug(
            "saving alias material_id=%s alias=%s",
            alias.material_id,
            alias.alias,
        )
        stmt = (
            insert(MaterialAliasORM)
            .values(
                id=uuid.uuid4(),
                material_id=alias.material_id.value,
                alias=alias.alias,
                weight=alias.weight,
            )
            .on_conflict_do_nothing(
                constraint="uq_material_aliases_material_id_alias",
            )
        )
        with translate_repo_exceptions(
            "MaterialAlias", f"{alias.material_id}:{alias.alias}"
        ):
            _ = self._session.execute(stmt)

    def find_by_id(self, material_id: MaterialId) -> Material | None:
        logger.debug("find_by_id material_id=%s", material_id)
        row = self._session.get(MaterialORM, material_id.value)
        if row is None:
            return None
        return self._to_domain(row)

    def find_by_slug(self, slug: str) -> Material | None:
        logger.debug("find_by_slug slug=%s", slug)
        stmt = select(MaterialORM).where(MaterialORM.slug == slug)
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return self._to_domain(row)

    def find_aliases_for(self, material_id: MaterialId) -> list[MaterialAlias]:
        logger.debug("find_aliases_for material_id=%s", material_id)
        stmt = select(MaterialAliasORM).where(
            MaterialAliasORM.material_id == material_id.value
        )
        rows = self._session.execute(stmt).scalars().all()
        return [
            MaterialAlias(
                material_id=MaterialId(row.material_id),
                alias=row.alias,
                weight=row.weight,
            )
            for row in rows
        ]

    def all_materials(self) -> list[Material]:
        logger.debug("all_materials")
        stmt = select(MaterialORM)
        rows = self._session.execute(stmt).scalars().all()
        return [self._to_domain(row) for row in rows]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_domain(row: MaterialORM) -> Material:
        return Material(
            id=MaterialId(row.id),
            canonical_name=row.canonical_name,
            slug=row.slug,
            category=MaterialCategory(row.category),
            parent_id=(
                MaterialId(row.parent_id) if row.parent_id is not None else None
            ),
        )
