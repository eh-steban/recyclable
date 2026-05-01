"""SQLAlchemy ORM model for regression / eval cases."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.models.base import Base


class RegressionCaseORM(Base):
    __tablename__ = "regression_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jurisdictions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    expected_material_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=True,
    )
    expected_status: Mapped[str] = mapped_column(String, nullable=False)
    expected_disposition: Mapped[str] = mapped_column(String, nullable=False)
    must_cite_source: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    refusal_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
