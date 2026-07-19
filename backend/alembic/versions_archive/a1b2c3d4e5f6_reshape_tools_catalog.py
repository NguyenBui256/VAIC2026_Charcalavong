"""reshape tools catalog + agent_tools

Revision ID: a1b2c3d4e5f6
Revises: c4f1a9d3e7b2
Create Date: 2026-07-18

Greenfield reset (Sub-project A): tools become a tenant-wide catalog; agents
reference them via agent_tools. Old agent-owned tool rows are demo-only and
are dropped + reseeded. Mirrors the RLS DDL of 9e84be8908a0.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "c4f1a9d3e7b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"


def _enable_rls(table: str, *, delete: bool = True) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_policy ON {table}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);"""
    )
    verbs = "SELECT, INSERT, UPDATE, DELETE" if delete else "SELECT, INSERT, UPDATE"
    op.execute(f"GRANT {verbs} ON {table} TO {APP_ROLE};")


def upgrade() -> None:
    # Drop the old agent-owned tools table (demo data only, reseeded later).
    op.execute("DROP TABLE IF EXISTS tools CASCADE;")

    op.create_table(
        "tools",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tool_type", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("params_schema", postgresql.JSONB(), nullable=False),
        sa.Column("output_schema", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("credential_ref", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("tool_type IN ('rag','gmail','calendar')", name="ck_tools_type"),
    )
    op.create_index("ix_tools_tenant_id", "tools", ["tenant_id"])
    _enable_rls("tools", delete=True)

    op.create_table(
        "agent_tools",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tool_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tools.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_tools_tenant_id", "agent_tools", ["tenant_id"])
    op.create_index("ix_agent_tools_tool_id", "agent_tools", ["tool_id"])
    _enable_rls("agent_tools", delete=True)


def downgrade() -> None:
    for t in ("agent_tools", "tools"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {t};")
        op.execute(f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;")
        op.drop_table(t)
