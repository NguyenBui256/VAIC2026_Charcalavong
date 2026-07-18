"""create action_bindings + action_events tables with RLS.

Tenant-isolation RLS (app.tenant_id GUC), mirroring
aa10database01_create_mini_app_databases.py. action_bindings = config
(database_id + event_type -> workflow_id); action_events = the row-change outbox.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ac20actions01"
down_revision: str | Sequence[str] | None = "ac10notify01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_policy ON {table}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);"""
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO vaic_app;")


def upgrade() -> None:
    op.create_table(
        "action_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("database_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("mini_app_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False, server_default="row.created"),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notify_user_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
                  nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_action_bindings_tenant_name"),
        sa.CheckConstraint("event_type IN ('row.created','row.updated','row.deleted')",
                           name="ck_action_bindings_event_type"),
    )
    op.create_index("ix_action_bindings_db_event", "action_bindings", ["database_id", "event_type"])
    _enable_rls("action_bindings")

    op.create_table(
        "action_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("app_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("mini_apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("database_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("row_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("completed_notified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending','dispatched','failed','skipped')",
                           name="ck_action_events_status"),
    )
    op.create_index("ix_action_events_tenant_status", "action_events", ["tenant_id", "status"])
    _enable_rls("action_events")


def downgrade() -> None:
    for table in ("action_events", "action_bindings"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_action_events_tenant_status", table_name="action_events")
    op.drop_table("action_events")
    op.drop_index("ix_action_bindings_db_event", table_name="action_bindings")
    op.drop_table("action_bindings")
