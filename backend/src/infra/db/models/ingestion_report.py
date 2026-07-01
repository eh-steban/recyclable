"""SQLAlchemy ORM model for IngestionReport rows."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.db.models.base import Base

_STATUSES = "('draft', 'pending_review', 'approved', 'rejected')"


class IngestionReportORM(Base):
    """ORM row for one ingestion report.

    Maps to ingestion_reports. Created at DRAFT status; transitions to
    pending_review after Validator passes; approved/rejected by a human
    reviewer (Part B).
    """

    __tablename__: str = "ingestion_reports"
    __table_args__: tuple[CheckConstraint] = (
        CheckConstraint(
            f"status IN {_STATUSES}",
            name="ingestion_reports_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    jurisdiction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jurisdictions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    seed_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_document_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    proposed_rule_changes: Mapped[object] = mapped_column(JSONB, nullable=True)
    conflicts: Mapped[object] = mapped_column(JSONB, nullable=True)
    missing_fields: Mapped[object] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        server_default=text("'draft'"),
    )
    reviewer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_name: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingestion_run_traces.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
