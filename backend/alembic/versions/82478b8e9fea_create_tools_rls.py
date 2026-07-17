"""create tools rls

Revision ID: 82478b8e9fea
Revises: 9e84be8908a0
Create Date: 2026-07-18 01:00:00.000000

Story 2.6: creates the ``tools`` table — Tools registered against an Agent
(display_name, header, input_schema, output_schema, optional embedded_python).
Mirrors the RLS + soft-delete grant DDL pattern of
``7e8b08b45590_create_agents_rls.py``.

Schema columns:
    id                UUID PK (UUID v7, generated app-side)
    agent_id          UUID NOT NULL FK agents.id ON DELETE CASCADE
    tenant_id         UUID NOT NULL FK tenants.id ON DELETE CASCADE
    department_id     UUID NOT NULL FK departments.id ON DELETE RESTRICT
    display_name      varchar(255) NOT NULL
    header            jsonb NOT NULL DEFAULT '{}'  (incl. auth — never echoed in full)
    input_schema      jsonb NOT NULL
    output_schema     jsonb NOT NULL
    embedded_python   text NULL  (NULL => MCP-routed; non-NULL => sandbox-routed)
    is_deleted        boolean NOT NULL DEFAULT false
    deleted_at        timestamptz NULL
    created_at        timestamptz NOT NULL DEFAULT now()
    updated_at        timestamptz NOT NULL DEFAULT now()

RLS (AD-2): ENABLE + FORCE + tenant_isolation_policy on tenant_id.

Soft-delete only (mirrors ``agents``): ``vaic_app`` gets SELECT, INSERT,
UPDATE; DELETE and TRUNCATE are explicitly REVOKEd.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "82478b8e9fea"
down_revision: str | Sequence[str] | None = "9e84be8908a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"
TABLE = "tools"


def upgrade() -> None:
    """Create tools table with RLS + soft-delete-only grants."""
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column(
            "header", postgresql.JSONB(), nullable=False, server_default="{}"
        ),
        sa.Column("input_schema", postgresql.JSONB(), nullable=False),
        sa.Column("output_schema", postgresql.JSONB(), nullable=False),
        sa.Column("embedded_python", sa.Text(), nullable=True),
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

    op.create_index("ix_tools_agent_id", TABLE, ["agent_id"])
    op.create_index("ix_tools_tenant_id", TABLE, ["tenant_id"])

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
