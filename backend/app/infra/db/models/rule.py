"""SQLAlchemy ORM model for recycling rules."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.models.base import Base

_DISPOSITIONS = (
    "('curbside_recycle', 'dropoff', 'compost', 'landfill', "
    "'hazardous_waste', 'donate', 'unknown')"
)
_ACCEPTED_STATUSES = "('accepted', 'rejected', 'conditional', 'unknown')"
_CONFIDENCES = "('high', 'medium', 'low')"


class RuleORM(Base):
    __tablename__ = "rules"
    __table_args__ = (
        CheckConstraint(f"disposition IN {_DISPOSITIONS}", name="ck_rules_disposition"),
        CheckConstraint(
            f"accepted_status IN {_ACCEPTED_STATUSES}", name="ck_rules_accepted_status"
        ),
        CheckConstraint(f"confidence IN {_CONFIDENCES}", name="ck_rules_confidence"),
        # Partial unique index: only one active rule per (jurisdiction, material).
        # Superseded rules (superseded_by IS NOT NULL) are exempt.
        Index(
            "uq_rules_active_per_jurisdiction_material",
            "jurisdiction_id",
            "material_id",
            unique=True,
            postgresql_where=text("superseded_by IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    jurisdiction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jurisdictions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    material_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    disposition: Mapped[str] = mapped_column(String, nullable=False)
    accepted_status: Mapped[str] = mapped_column(String, nullable=False)
    preparation_steps: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    exceptions: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    warnings: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("ARRAY[]::text[]")
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_quote: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("'high'")
    )
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rules.id", ondelete="RESTRICT"),
        nullable=True,
    )
