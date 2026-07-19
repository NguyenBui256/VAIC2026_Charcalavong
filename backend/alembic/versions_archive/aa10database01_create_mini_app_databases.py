"""create mini_app_databases + mini_apps.database_id with RLS.

Tenant-isolation RLS only (app.tenant_id GUC), mirroring
c4f1a9d3e7b2_create_mini_apps_rls.py. A mini_app_databases row is a reusable
entity-schema template referenced by mini_apps.database_id (SET NULL on delete).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "aa10database01"
# Merge the two pre-existing heads (shared_pool_reshape + grant_delete_graph_...)
# so `alembic upgrade head` resolves to a single head.
down_revision: str | Sequence[str] | None = ("2848501cd966", "f7a8b9c0d1e2")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"


def upgrade() -> None:
    op.create_table(
        "mini_app_databases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("entity_schema", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_mini_app_databases_tenant_name"),
    )
    op.create_index("ix_mini_app_databases_tenant_id", "mini_app_databases", ["tenant_id"])

    op.execute("ALTER TABLE mini_app_databases ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE mini_app_databases FORCE ROW LEVEL SECURITY;")
    op.execute(
        """CREATE POLICY tenant_isolation_policy ON mini_app_databases
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);"""
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON mini_app_databases TO vaic_app;")

    op.add_column(
        "mini_apps",
        sa.Column(
            "database_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mini_app_databases.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("mini_apps", "database_id")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON mini_app_databases;")
    op.execute("ALTER TABLE mini_app_databases NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE mini_app_databases DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_mini_app_databases_tenant_id", table_name="mini_app_databases")
    op.drop_table("mini_app_databases")
