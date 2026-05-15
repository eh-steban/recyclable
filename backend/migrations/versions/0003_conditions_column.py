"""0003 conditions column -- add nullable conditions JSONB to audit records.

Adds a nullable `conditions jsonb` column to answer_audit_records so
that Accepted verdicts with conditions round-trip faithfully through
find_by_id (Phase 5.3). Also extends the answer_no_evaluation_reason
enum with the three missing variants: llm_rejected, uncertain_material,
conflicted.

Revision ID: 0003_conditions_column
Revises: 0002_answer_audit_record_columns
Create Date: 2026-05-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_conditions_column"
down_revision = "0002_answer_audit_record_columns"
branch_labels = None
depends_on = None

_NO_EVAL_REASON_TYPE = "answer_no_evaluation_reason"


def upgrade() -> None:
    # Extend the no_evaluation_reason enum with three missing variants.
    # ALTER TYPE ... ADD VALUE is transactional in Postgres 12+.
    op.execute(
        f"ALTER TYPE {_NO_EVAL_REASON_TYPE} "
        "ADD VALUE IF NOT EXISTS 'llm_rejected'"
    )
    op.execute(
        f"ALTER TYPE {_NO_EVAL_REASON_TYPE} "
        "ADD VALUE IF NOT EXISTS 'uncertain_material'"
    )
    op.execute(
        f"ALTER TYPE {_NO_EVAL_REASON_TYPE} "
        "ADD VALUE IF NOT EXISTS 'conflicted'"
    )

    # Add the conditions JSONB column (nullable -- existing rows have
    # NULL, meaning no conditions tuple was recorded).
    op.add_column(
        "answer_audit_records",
        sa.Column(
            "conditions",
            postgresql.JSONB(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("answer_audit_records", "conditions")

    # Postgres does not support removing enum values; downgrade leaves the
    # three added enum values in place. If a clean rollback to the exact
    # pre-0003 type is required, drop and recreate the enum manually.
