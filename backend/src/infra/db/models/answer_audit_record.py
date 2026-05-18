"""SQLAlchemy ORM model for AnswerAuditRecord rows.

Column shape per design D6 (01-sonnet-user-path.design.md).  Migration
0002 reshapes the Step 1 answer_audit_records table to this schema.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.db.models.base import Base

# JSON-compatible dict stored in JSONB columns.
JsonDict = dict[str, object]

# Enum value sets pinned to the design (D6) and spec contracts.
# verdict: wire-shaped answer verdict (answer.md § Verdict mapping)
VerdictEnum = Enum(
    "yes",
    "no",
    "conditional",
    "unknown",
    name="answer_verdict",
)

# outcome_kind: whether the record represents an evaluated or refused answer
OutcomeKindEnum = Enum(
    "evaluated",
    "no_evaluation",
    name="answer_outcome_kind",
)

# no_evaluation_reason: cause of a NoEvaluation outcome (nullable).
# All six NoEvaluationReason variants are represented here so the
# write path can persist any outcome.
NoEvaluationReasonEnum = Enum(
    "out_of_jurisdiction",
    "no_evidence",
    "validator_rejected",
    "llm_rejected",
    "uncertain_material",
    "conflicted",
    name="answer_no_evaluation_reason",
)


class AnswerAuditRecordORM(Base):
    """ORM row for one user-path invocation.

    Maps to answer_audit_records (INV-PROD-003).  Every row is
    append-only; no UPDATE path exists on the user path.  Persisted
    before the HTTP response is returned so that every definitive answer
    is auditable (INV-PROD-001).
    """

    __tablename__: str = "answer_audit_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_location_input: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jurisdictions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    verdict: Mapped[str] = mapped_column(VerdictEnum, nullable=False)
    outcome_kind: Mapped[str] = mapped_column(OutcomeKindEnum, nullable=False)
    no_evaluation_reason: Mapped[str | None] = mapped_column(
        NoEvaluationReasonEnum, nullable=True
    )
    conditions: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True, default=None
    )
    recommended_action: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("''")
    )
    citations: Mapped[JsonDict] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'")
    )
    validator_findings: Mapped[JsonDict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
