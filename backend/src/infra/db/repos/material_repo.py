"""Repo for materials and aliases."""

import logging
import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.domain.knowledge_base.material import Material, MaterialAlias
from src.infra.db.models.material import MaterialORM
from src.infra.db.models.material_alias import MaterialAliasORM

logger = logging.getLogger(__name__)


class SqlMaterialRepo:
    _session: Session

    def __init__(self, session: Session) -> None:
        self._session = session

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
        _ = self._session.execute(stmt)
