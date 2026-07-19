"""create mini_apps + mini_app_rows with RLS (Epic 4, stories 4-2/4-3).

Tenant-isolation RLS only (app.tenant_id GUC), mirroring
1ad51bb8e8cb_create_workflows_rls.py. Visibility tier is enforced at the
app layer (spec §4).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c4f1a9d3e7b2"
down_revision: str | Sequence[str] | None = "39dfa51cec0c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"


def _enable_rls(table: str, *, with_delete: bool) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_policy ON {table}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);"""
    )
    grants = "SELECT, INSERT, UPDATE, DELETE" if with_delete else "SELECT, INSERT, UPDATE"
    op.execute(f"GRANT {grants} ON {table} TO {APP_ROLE};")


def upgrade() -> None:
    op.create_table(
        "mini_apps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("entity_schema", postgresql.JSONB(), nullable=False),
        sa.Column("ui_spec", postgresql.JSONB(), nullable=False),
        sa.Column("visibility_tier", sa.String(16), nullable=False, server_default="need_auth"),
        sa.Column("whitelist_user_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
                  nullable=False, server_default="{}"),
        sa.Column("build_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("build_error", sa.Text(), nullable=True),
        sa.Column("bundle_path", sa.Text(), nullable=True),
        sa.Column("created_by_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "visibility_tier IN ('public','need_auth','private')",
            name="ck_mini_apps_visibility_tier",
        ),
        sa.CheckConstraint(
            "build_status IN ('pending','building','ready','failed')",
            name="ck_mini_apps_build_status",
        ),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_mini_apps_tenant_slug"),
    )
    op.create_index("ix_mini_apps_tenant_id", "mini_apps", ["tenant_id"])

    op.create_table(
        "mini_app_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("app_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("mini_apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_mini_app_rows_app_id", "mini_app_rows", ["app_id"])
    op.create_index("ix_mini_app_rows_tenant_id", "mini_app_rows", ["tenant_id"])

    _enable_rls("mini_apps", with_delete=True)
    _enable_rls("mini_app_rows", with_delete=True)


def downgrade() -> None:
    for table in ("mini_app_rows", "mini_apps"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
    op.drop_table("mini_app_rows")
    op.drop_table("mini_apps")
