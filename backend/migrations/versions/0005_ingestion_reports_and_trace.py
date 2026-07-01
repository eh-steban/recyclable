"""0005 ingestion reports and trace.

Creates ingestion_reports and ingestion_run_traces with their full column
sets per data-model.md and design D6. Story 1 populates only the minimal
trace fields (id, seed_url, created_at); Stories 2-4 populate the rest --
no follow-up migration needed.

Revision ID: 0005_ingestion_reports_and_trace
Revises: 0004_pg_trgm_index
Create Date: 2026-07-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_ingestion_reports_and_trace"
down_revision = "0004_pg_trgm_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- ingestion_run_traces ----
    # Created before ingestion_reports because reports holds a non-null FK
    # to traces; drop order is reversed.
    _ = op.create_table(
        "ingestion_run_traces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("seed_url", sa.Text(), nullable=False),
        # Full D6 audit columns -- populated by Stories 2-4.
        sa.Column("tool_calls", postgresql.JSONB(), nullable=True),
        sa.Column(
            "urls_fetched",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
        ),
        sa.Column("extraction_outputs", postgresql.JSONB(), nullable=True),
        sa.Column("diff_summary", postgresql.JSONB(), nullable=True),
        sa.Column("iteration_count", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "estimated_cost",
            sa.Numeric(precision=10, scale=6),
            nullable=True,
        ),
        sa.Column("errors", postgresql.JSONB(), nullable=True),
        sa.Column(
            "source_documents_payload", postgresql.JSONB(), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ---- ingestion_reports ----
    _ = op.create_table(
        "ingestion_reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "jurisdiction_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("seed_url", sa.Text(), nullable=False),
        sa.Column(
            "source_document_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=True,
        ),
        sa.Column("proposed_rule_changes", postgresql.JSONB(), nullable=True),
        sa.Column("conflicts", postgresql.JSONB(), nullable=True),
        sa.Column("missing_fields", postgresql.JSONB(), nullable=True),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("reviewer_id", sa.Text(), nullable=True),
        sa.Column("prompt_name", sa.String(), nullable=True),
        sa.Column("prompt_version", sa.Integer(), nullable=True),
        sa.Column("model_id", sa.String(), nullable=True),
        # Non-null FK to the run trace minted at run start.
        sa.Column(
            "trace_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'pending_review', 'approved', 'rejected')",
            name="ingestion_reports_status",
        ),
        sa.ForeignKeyConstraint(
            ["jurisdiction_id"],
            ["jurisdictions.id"],
            name="fk_ingestion_reports_jurisdiction_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["trace_id"],
            ["ingestion_run_traces.id"],
            name="fk_ingestion_reports_trace_id",
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    # FK-safe order: drop reports before traces.
    op.drop_table("ingestion_reports")
    op.drop_table("ingestion_run_traces")
