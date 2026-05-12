"""0001 data spine -- 7 in-scope tables for experiment 01-grounded-retrieval.

Revision ID: 0001_data_spine
Revises:
Create Date: 2026-04-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_data_spine"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- jurisdictions ----
    _ = op.create_table(
        "jurisdictions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("supported_status", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "type IN ('city', 'county', 'state')", name="ck_jurisdictions_type"
        ),
        sa.CheckConstraint(
            "supported_status IN ('supported', 'coming_soon', 'unsupported')",
            name="ck_jurisdictions_supported_status",
        ),
        sa.UniqueConstraint("slug", name="uq_jurisdictions_slug"),
    )

    # ---- materials ----
    _ = op.create_table(
        "materials",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("canonical_name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            (
                "category IN ('glass', 'plastic', 'metal', 'paper',"
                " 'organic', 'hazardous', 'electronic', 'textile', 'other')"
            ),
            name="ck_materials_category",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["materials.id"],
            name="fk_materials_parent_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("slug", name="uq_materials_slug"),
    )

    # ---- material_aliases ----
    _ = op.create_table(
        "material_aliases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alias", sa.String(), nullable=False),
        sa.Column(
            "weight", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.ForeignKeyConstraint(
            ["material_id"],
            ["materials.id"],
            name="fk_material_aliases_material_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "material_id", "alias", name="uq_material_aliases_material_id_alias"
        ),
    )

    # ---- source_documents ----
    _ = op.create_table(
        "source_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "jurisdiction_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("authority_level", sa.Integer(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("source_text_hash", sa.String(64), nullable=False),
        sa.Column(
            "last_reviewed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["jurisdiction_id"],
            ["jurisdictions.id"],
            name="fk_source_documents_jurisdiction_id",
            ondelete="RESTRICT",
        ),
    )

    # ---- rules ----
    _ = op.create_table(
        "rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "jurisdiction_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("material_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("disposition", sa.String(), nullable=False),
        sa.Column("accepted_status", sa.String(), nullable=False),
        sa.Column(
            "preparation_steps",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column(
            "exceptions",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column(
            "warnings",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column(
            "source_document_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("source_quote", sa.Text(), nullable=False),
        sa.Column(
            "confidence",
            sa.String(),
            nullable=False,
            server_default=sa.text("'high'"),
        ),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column(
            "superseded_by", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.CheckConstraint(
            (
                "disposition IN ('curbside_recycle', 'dropoff', 'compost',"
                " 'landfill', 'hazardous_waste', 'donate', 'unknown')"
            ),
            name="ck_rules_disposition",
        ),
        sa.CheckConstraint(
            (
                "accepted_status IN"
                " ('accepted', 'rejected', 'conditional', 'unknown')"
            ),
            name="ck_rules_accepted_status",
        ),
        sa.CheckConstraint(
            "confidence IN ('high', 'medium', 'low')",
            name="ck_rules_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["jurisdiction_id"],
            ["jurisdictions.id"],
            name="fk_rules_jurisdiction_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["material_id"],
            ["materials.id"],
            name="fk_rules_material_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["source_documents.id"],
            name="fk_rules_source_document_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by"],
            ["rules.id"],
            name="fk_rules_superseded_by",
            ondelete="RESTRICT",
        ),
    )
    # Regular indexes on FK columns used for filtering.
    op.create_index("ix_rules_jurisdiction_id", "rules", ["jurisdiction_id"])
    op.create_index("ix_rules_material_id", "rules", ["material_id"])
    # Partial unique index: only one active rule per (jurisdiction, material).
    op.create_index(
        "uq_rules_active_per_jurisdiction_material",
        "rules",
        ["jurisdiction_id", "material_id"],
        unique=True,
        postgresql_where=sa.text("superseded_by IS NULL"),
    )

    # ---- regression_cases ----
    _ = op.create_table(
        "regression_cases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column(
            "jurisdiction_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "expected_material_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("expected_status", sa.String(), nullable=False),
        sa.Column("expected_disposition", sa.String(), nullable=False),
        sa.Column(
            "must_cite_source",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "refusal_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["jurisdiction_id"],
            ["jurisdictions.id"],
            name="fk_regression_cases_jurisdiction_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["expected_material_id"],
            ["materials.id"],
            name="fk_regression_cases_expected_material_id",
            ondelete="RESTRICT",
        ),
    )

    # ---- answer_audit_records ----
    _ = op.create_table(
        "answer_audit_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_query", sa.Text(), nullable=False),
        sa.Column(
            "jurisdiction_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "normalized_materials",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        ),
        sa.Column(
            "retrieved_rule_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        ),
        sa.Column(
            "retrieved_source_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("ARRAY[]::uuid[]"),
        ),
        sa.Column("prompt_name", sa.String(), nullable=False),
        sa.Column("prompt_version", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column(
            "raw_model_output",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "final_answer",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "validator_result",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("confidence", sa.String(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "cache_hit",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["jurisdiction_id"],
            ["jurisdictions.id"],
            name="fk_answer_audit_records_jurisdiction_id",
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    # Drop in reverse FK-safe order.
    op.drop_table("answer_audit_records")
    op.drop_table("regression_cases")
    op.drop_index(
        "uq_rules_active_per_jurisdiction_material", table_name="rules"
    )
    op.drop_index("ix_rules_material_id", table_name="rules")
    op.drop_index("ix_rules_jurisdiction_id", table_name="rules")
    op.drop_table("rules")
    op.drop_table("source_documents")
    op.drop_table("material_aliases")
    op.drop_table("materials")
    op.drop_table("jurisdictions")
