"""0002 answer_audit_record columns -- reshape to D6 schema.

Drops the Step 1 placeholder columns from answer_audit_records and adds
the D6 column set aligned with AnswerAuditRecordORM and the answer
contract (private/specs/contracts/answer.md).

The table is empty in every known environment, so the migration drops
and recreates columns without any data migration.

Revision ID: 0002_answer_audit_record_columns
Revises: 0001_data_spine
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_answer_audit_record_columns"
down_revision = "0001_data_spine"
branch_labels = None
depends_on = None

# Enum type definitions.
_VERDICT_TYPE = "answer_verdict"
_OUTCOME_KIND_TYPE = "answer_outcome_kind"
_NO_EVAL_REASON_TYPE = "answer_no_evaluation_reason"


def upgrade() -> None:
    # -- Create enum types (must exist before the columns that use them) ------

    verdict_enum = postgresql.ENUM(
        "yes",
        "no",
        "conditional",
        "unknown",
        name=_VERDICT_TYPE,
    )
    verdict_enum.create(op.get_bind(), checkfirst=True)

    outcome_kind_enum = postgresql.ENUM(
        "evaluated",
        "no_evaluation",
        name=_OUTCOME_KIND_TYPE,
    )
    outcome_kind_enum.create(op.get_bind(), checkfirst=True)

    no_eval_reason_enum = postgresql.ENUM(
        "out_of_jurisdiction",
        "no_evidence",
        "validator_rejected",
        name=_NO_EVAL_REASON_TYPE,
    )
    no_eval_reason_enum.create(op.get_bind(), checkfirst=True)

    # -- Drop Step 1 columns --------------------------------------------------

    op.drop_column("answer_audit_records", "user_query")
    op.drop_column("answer_audit_records", "normalized_materials")
    op.drop_column("answer_audit_records", "retrieved_rule_ids")
    op.drop_column("answer_audit_records", "retrieved_source_ids")
    op.drop_column("answer_audit_records", "prompt_name")
    op.drop_column("answer_audit_records", "prompt_version")
    op.drop_column("answer_audit_records", "raw_model_output")
    op.drop_column("answer_audit_records", "final_answer")
    op.drop_column("answer_audit_records", "validator_result")
    op.drop_column("answer_audit_records", "confidence")
    op.drop_column("answer_audit_records", "cache_hit")

    # -- Add D6 columns -------------------------------------------------------

    op.add_column(
        "answer_audit_records",
        sa.Column("query_text", sa.Text(), nullable=False),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column("query_location_input", sa.Text(), nullable=False),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column(
            "verdict",
            sa.Enum(
                "yes",
                "no",
                "conditional",
                "unknown",
                name=_VERDICT_TYPE,
                create_type=False,
            ),
            nullable=False,
        ),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column(
            "outcome_kind",
            sa.Enum(
                "evaluated",
                "no_evaluation",
                name=_OUTCOME_KIND_TYPE,
                create_type=False,
            ),
            nullable=False,
        ),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column(
            "no_evaluation_reason",
            sa.Enum(
                "out_of_jurisdiction",
                "no_evidence",
                "validator_rejected",
                name=_NO_EVAL_REASON_TYPE,
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column(
            "recommended_action",
            sa.Text(),
            nullable=False,
            server_default=sa.text("''"),
        ),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column(
            "citations",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column(
            "validator_findings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column("prompt_version", sa.String(), nullable=False),
    )
    # model_id and latency_ms already exist from Step 1 with the same
    # types D6 requires (model_id: VARCHAR NOT NULL; latency_ms:
    # INTEGER nullable); preserve them rather than drop-and-recreate.


def downgrade() -> None:
    # -- Drop D6 columns ------------------------------------------------------
    # model_id and latency_ms were preserved across upgrade(); leave them
    # in place on downgrade as well -- they belong to both schemas.

    op.drop_column("answer_audit_records", "prompt_version")
    op.drop_column("answer_audit_records", "validator_findings")
    op.drop_column("answer_audit_records", "citations")
    op.drop_column("answer_audit_records", "recommended_action")
    op.drop_column("answer_audit_records", "no_evaluation_reason")
    op.drop_column("answer_audit_records", "outcome_kind")
    op.drop_column("answer_audit_records", "verdict")
    op.drop_column("answer_audit_records", "query_location_input")
    op.drop_column("answer_audit_records", "query_text")

    # -- Drop enum types ------------------------------------------------------

    op.execute(f"DROP TYPE IF EXISTS {_NO_EVAL_REASON_TYPE}")
    op.execute(f"DROP TYPE IF EXISTS {_OUTCOME_KIND_TYPE}")
    op.execute(f"DROP TYPE IF EXISTS {_VERDICT_TYPE}")

    # -- Restore Step 1 columns -----------------------------------------------

    op.add_column(
        "answer_audit_records",
        sa.Column("user_query", sa.Text(), nullable=False),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column(
            "normalized_materials",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        ),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column(
            "retrieved_rule_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        ),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column(
            "retrieved_source_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        ),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column("prompt_name", sa.String(), nullable=False),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column("prompt_version", sa.Integer(), nullable=False),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column(
            "raw_model_output",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column(
            "final_answer",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column(
            "validator_result",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column("confidence", sa.String(), nullable=True),
    )
    op.add_column(
        "answer_audit_records",
        sa.Column(
            "cache_hit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
