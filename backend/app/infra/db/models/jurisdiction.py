"""SQLAlchemy ORM model for jurisdictions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.models.base import Base

_JURISDICTION_TYPES = "('city', 'county', 'state')"
_SUPPORTED_STATUSES = "('supported', 'coming_soon', 'unsupported')"


class JurisdictionORM(Base):
    __tablename__ = "jurisdictions"
    __table_args__ = (
        CheckConstraint(f"type IN {_JURISDICTION_TYPES}", name="ck_jurisdictions_type"),
        CheckConstraint(
            f"supported_status IN {_SUPPORTED_STATUSES}",
            name="ck_jurisdictions_supported_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    supported_status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
