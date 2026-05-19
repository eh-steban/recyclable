"""0004 pg_trgm index -- enable trigram similarity on material_aliases.alias.

Creates the pg_trgm extension and a GIN trigram index on
material_aliases.alias. This enables the pg_trgm similarity() function
used by PgMaterialAliasSearch (the MaterialAliasSearch port implementation)
in Step 1 of MaterialNormalizerService.

Revision ID: 0004_pg_trgm_index
Revises: 0003_conditions_column
Create Date: 2026-05-18
"""

from alembic import op

revision = "0004_pg_trgm_index"
down_revision = "0003_conditions_column"
branch_labels = None
depends_on = None

_GIN_INDEX = "ix_material_aliases_alias_trgm"


def upgrade() -> None:
    # Enable the pg_trgm extension (idempotent; no-op if already present).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # GIN trigram index on material_aliases.alias for fast similarity().
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {_GIN_INDEX}"
        " ON material_aliases USING GIN (alias gin_trgm_ops);"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {_GIN_INDEX};")

    # pg_trgm extension is intentionally NOT dropped on downgrade.
    # It is a shared extension that may be used by other indexes or
    # queries outside this feature. Removing it here would silently
    # break other callers. If the extension must be removed, do so
    # manually after confirming no other consumers depend on it.
