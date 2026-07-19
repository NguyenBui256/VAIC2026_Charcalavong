"""shared pool reshape

Revision ID: 2848501cd966
Revises: b2c3d4e5f6a7
Create Date: 2026-07-18 18:00:36.717668

Sub-project A follow-up: Tools/API Integrations/Knowledge Base move to a
shared-tenant pool managed by `builder` role (see Task 2 model changes).

    - `api_integrations` loses `agent_id` — becomes tenant-scoped (no longer
      tied to a single Agent). FK `api_integrations_agent_id_fkey` (confirmed
      via `\\d api_integrations` on dev DB) + column dropped.
    - `tools` gains `kind` (builtin|integration, default builtin) and
      `integration_id` (nullable FK -> api_integrations.id, ON DELETE
      RESTRICT — an integration in use by a tool cannot be deleted).
    - `kb_document_grants` (user-level KB access grants) is dropped; KB
      access becomes builder-managed (CRUD gate) + agent-level grants via
      `agent_kb_documents` only.

Verified against dev DB (`\\d api_integrations`, `\\d tools`,
`\\d kb_document_grants` at head b2c3d4e5f6a7): FK name
`api_integrations_agent_id_fkey` is correct; `tools` has neither `kind` nor
`integration_id` yet (an earlier divergent migration f3a1c9e7b2d4 added a
column of the same name but the table was fully recreated by
a1b2c3d4e5f6, so no collision).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '2848501cd966'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "vaic_app"


def upgrade() -> None:
    """Upgrade schema."""
    # 1. api_integrations -> tenant-scope: drop agent_id (+ FK + its index).
    #    RLS already scopes on tenant_id; no policy change needed.
    op.drop_index("ix_api_integrations_agent_id", table_name="api_integrations")
    op.drop_constraint(
        "api_integrations_agent_id_fkey", "api_integrations", type_="foreignkey"
    )
    op.drop_column("api_integrations", "agent_id")

    # 2. tools: add kind + integration_id
    op.add_column(
        "tools",
        sa.Column(
            "kind", sa.String(16), nullable=False, server_default="builtin"
        ),
    )
    op.add_column(
        "tools",
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_tools_integration_id", "tools", ["integration_id"])
    op.create_foreign_key(
        "tools_integration_id_fkey",
        "tools",
        "api_integrations",
        ["integration_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 3. drop user-level KB grants (RLS + policy dropped with the table)
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON kb_document_grants;")
    op.execute("ALTER TABLE kb_document_grants NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE kb_document_grants DISABLE ROW LEVEL SECURITY;")
    op.drop_table("kb_document_grants")


def downgrade() -> None:
    """Downgrade schema."""
    # 3. re-create kb_document_grants (mirrors b2c3d4e5f6a7 upgrade())
    op.create_table(
        "kb_document_grants",
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("kb_documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("role IN ('viewer','manager')", name="ck_kb_grant_role"),
    )
    op.create_index("ix_kb_document_grants_tenant_id", "kb_document_grants", ["tenant_id"])
    op.create_index("ix_kb_document_grants_user_id", "kb_document_grants", ["user_id"])
    op.execute("ALTER TABLE kb_document_grants ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE kb_document_grants FORCE ROW LEVEL SECURITY;")
    op.execute(
        """CREATE POLICY tenant_isolation_policy ON kb_document_grants
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);"""
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON kb_document_grants TO {APP_ROLE};")

    # 2. tools: drop integration_id + kind
    op.drop_constraint("tools_integration_id_fkey", "tools", type_="foreignkey")
    op.drop_index("ix_tools_integration_id", table_name="tools")
    op.drop_column("tools", "integration_id")
    op.drop_column("tools", "kind")

    # 1. api_integrations: re-add agent_id (nullable — cannot backfill which
    #    agent an integration "belonged" to once tenant-scoped; a stricter
    #    NOT NULL + FK is not re-derivable from data alone)
    op.add_column(
        "api_integrations",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "api_integrations_agent_id_fkey",
        "api_integrations",
        "agents",
        ["agent_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_api_integrations_agent_id", "api_integrations", ["agent_id"])
