"""create workflows rls

Revision ID: 1ad51bb8e8cb
Revises: f3a1c9e7b2d4
Create Date: 2026-07-18 04:21:11.584367

Story 3.1: creates the ``workflows`` table — Epic 3's first migration.
Mirrors the RLS + grant DDL pattern of
``82478b8e9fea_create_tools_rls.py`` / ``7e8b08b45590_create_agents_rls.py``.

Schema columns:
    id                          UUID PK (UUID v7, generated app-side)
    tenant_id                   UUID NOT NULL FK tenants.id ON DELETE CASCADE
    owner_id                    UUID NOT NULL FK users.id ON DELETE RESTRICT
    name                        varchar(255) NOT NULL
    description                 text NOT NULL  (opaque run-time hint, AC2)
    constraints                 jsonb NOT NULL DEFAULT '[]'
    confidence_threshold        float NOT NULL DEFAULT 0.7   (pre-provisioned for Story 3.5)
    escalation_timeout_seconds  integer NOT NULL DEFAULT 300 (pre-provisioned for Story 3.6)
    version                     integer NOT NULL DEFAULT 1
    created_at                  timestamptz NOT NULL DEFAULT now()
    updated_at                  timestamptz NOT NULL DEFAULT now()

RLS (AD-2): ENABLE + FORCE + tenant_isolation_policy on tenant_id.

No soft-delete column — Workflows are not soft-deletable per Story 3.1's
ACs. Grants: SELECT, INSERT, UPDATE only (no DELETE needed).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1ad51bb8e8cb"
down_revision: str | Sequence[str] | None = "f3a1c9e7b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"
TABLE = "workflows"


def upgrade() -> None:
    """Create workflows table with RLS + CRUD-only grants."""
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
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "constraints", postgresql.JSONB(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "confidence_threshold",
            sa.Float(),
            nullable=False,
            server_default="0.7",
        ),
        sa.Column(
            "escalation_timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default="300",
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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

    op.create_index("ix_workflows_tenant_id", TABLE, ["tenant_id"])

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

    # --- CRUD grant to vaic_app (no DELETE needed) -------------------------
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {TABLE} TO {APP_ROLE};")


def downgrade() -> None:
    """Reverse: drop policy, disable RLS, drop table."""
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {TABLE};")
    op.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;")
    op.drop_table(TABLE)
