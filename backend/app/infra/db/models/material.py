"""SQLAlchemy ORM model for materials."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.models.base import Base

_CATEGORIES = (
    "('glass', 'plastic', 'metal', 'paper', 'organic', "
    "'hazardous', 'electronic', 'textile', 'other')"
)


class MaterialORM(Base):
    __tablename__: str = "materials"
    __table_args__: tuple[CheckConstraint, ...] = (
        CheckConstraint(
            f"category IN {_CATEGORIES}", name="ck_materials_category"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=True,
    )
