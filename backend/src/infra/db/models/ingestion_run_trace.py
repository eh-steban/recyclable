"""SQLAlchemy ORM model for IngestionRunTrace rows."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.db.models.base import Base


class IngestionRunTraceORM(Base):
    """ORM row for one ingestion run audit trace.

    Story 1 populates only id, seed_url, created_at.
    Stories 2-4 populate the remaining D6 columns (tool_calls, etc.).
    """

    __tablename__: str = "ingestion_run_traces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    seed_url: Mapped[str] = mapped_column(Text, nullable=False)
    # Full D6 audit columns -- populated by Stories 2-4.
    tool_calls: Mapped[object] = mapped_column(JSONB, nullable=True)
    urls_fetched: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    extraction_outputs: Mapped[object] = mapped_column(JSONB, nullable=True)
    diff_summary: Mapped[object] = mapped_column(JSONB, nullable=True)
    iteration_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[object] = mapped_column(Numeric, nullable=True)
    errors: Mapped[object] = mapped_column(JSONB, nullable=True)
    source_documents_payload: Mapped[object] = mapped_column(
        JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
