"""create agents rls

Revision ID: 7e8b08b45590
Revises: 34cd8281e2b3
Create Date: 2026-07-17 23:02:34.978120

Story 2.1: creates the ``agents`` table — Specialist Agent identity +
department scoping (foundation for Epic 2). Mirrors the RLS + grant DDL
pattern of ``34cd8281e2b3_create_audit_trail_table.py``.

Schema columns:
    id             UUID PK (UUID v7, generated app-side)
    tenant_id      UUID NOT NULL FK tenants.id ON DELETE CASCADE
    department_id  UUID NOT NULL FK departments.id ON DELETE RESTRICT
    owner_id       UUID NOT NULL FK users.id ON DELETE RESTRICT
    name           varchar(255) NOT NULL
    system_prompt  text NOT NULL
    status         varchar(32) NOT NULL DEFAULT 'draft'
    version        integer NOT NULL DEFAULT 1
    is_deleted     boolean NOT NULL DEFAULT false
    deleted_at     timestamptz NULL
    created_at     timestamptz NOT NULL DEFAULT now()
    updated_at     timestamptz NOT NULL DEFAULT now()

RLS (AD-2, AC9): ENABLE + FORCE + tenant_isolation_policy on tenant_id.

Soft-delete only (AC7, AD-4 append-only style): ``vaic_app`` gets SELECT,
INSERT, UPDATE; DELETE and TRUNCATE are explicitly REVOKEd so a stray hard
delete fails at the DB — enforcing soft-delete via ``is_deleted``.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7e8b08b45590"
down_revision: str | Sequence[str] | None = "34cd8281e2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"
TABLE = "agents"


def upgrade() -> None:
    """Create agents table with RLS + soft-delete-only grants."""
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
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="draft"
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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

    op.create_index("ix_agents_tenant_id", TABLE, ["tenant_id"])
    op.create_index("ix_agents_department_id", TABLE, ["department_id"])

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

    # --- Soft-delete-only grant to vaic_app (AC7) --------------------------
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {TABLE} TO {APP_ROLE};")
    op.execute(f"REVOKE DELETE ON {TABLE} FROM {APP_ROLE};")
    op.execute(f"REVOKE TRUNCATE ON {TABLE} FROM {APP_ROLE};")


def downgrade() -> None:
    """Reverse: drop policy, disable RLS, drop table."""
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {TABLE};")
    op.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;")
    op.drop_table(TABLE)
