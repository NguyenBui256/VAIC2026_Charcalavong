"""create api_integrations rls

Revision ID: dbbf3cb533e9
Revises: 82478b8e9fea
Create Date: 2026-07-18 02:31:30.615390

Story 2.7: creates the ``api_integrations`` table — reusable, named HTTP
connections registered against an Agent (name, base_url, encrypted auth
header, schema, last_used_at). Mirrors the RLS + soft-delete grant DDL
pattern of ``82478b8e9fea_create_tools_rls.py``.

Schema columns:
    id                      UUID PK (UUID v7, generated app-side)
    tenant_id               UUID NOT NULL FK tenants.id ON DELETE CASCADE
    agent_id                UUID NOT NULL FK agents.id ON DELETE CASCADE
    name                    varchar(255) NOT NULL
    base_url                varchar(2048) NOT NULL
    auth_header_encrypted   text NOT NULL  (ciphertext only — NEVER plaintext)
    schema                  jsonb NULL
    last_used_at            timestamptz NULL
    is_deleted              boolean NOT NULL DEFAULT false
    deleted_at              timestamptz NULL
    created_at              timestamptz NOT NULL DEFAULT now()
    updated_at              timestamptz NOT NULL DEFAULT now()

RLS (AD-2): ENABLE + FORCE + tenant_isolation_policy on tenant_id.

Soft-delete only (mirrors ``tools``/``agents``): ``vaic_app`` gets SELECT,
INSERT, UPDATE; DELETE and TRUNCATE are explicitly REVOKEd.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dbbf3cb533e9"
down_revision: str | Sequence[str] | None = "82478b8e9fea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"
TABLE = "api_integrations"


def upgrade() -> None:
    """Create api_integrations table with RLS + soft-delete-only grants."""
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("base_url", sa.String(2048), nullable=False),
        sa.Column("auth_header_encrypted", sa.Text(), nullable=False),
        sa.Column("schema", postgresql.JSONB(), nullable=True),
        sa.Column("last_used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index("ix_api_integrations_tenant_id", TABLE, ["tenant_id"])
    op.create_index("ix_api_integrations_agent_id", TABLE, ["agent_id"])

    # --- RLS: ENABLE + FORCE + policy -------------------------------------
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_policy
            ON {TABLE}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
        """
    )

    # --- Soft-delete-only grant to vaic_app --------------------------------
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {TABLE} TO {APP_ROLE};")
    op.execute(f"REVOKE DELETE ON {TABLE} FROM {APP_ROLE};")
    op.execute(f"REVOKE TRUNCATE ON {TABLE} FROM {APP_ROLE};")


def downgrade() -> None:
    """Reverse: drop policy, disable RLS, drop table."""
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {TABLE};")
    op.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;")
    op.drop_table(TABLE)
