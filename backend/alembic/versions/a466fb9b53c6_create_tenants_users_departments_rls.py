"""create tenants users departments rls

Revision ID: a466fb9b53c6
Revises:
Create Date: 2026-07-17 19:45:44.563361

Implements AD-2: every tenant-scoped table has ENABLE + FORCE ROW LEVEL
SECURITY with a policy using `current_setting('app.tenant_id')::uuid`. The
application role `vaic_app` is created with BYPASSRLS NOT granted (and
explicitly revoked if it somehow had it).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a466fb9b53c6"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# --- Names ----------------------------------------------------------------
APP_ROLE = "vaic_app"

TENANT_SCOPED_TABLES = ("departments", "users")
# `tenants` is itself the boundary; its policy uses `id` not `tenant_id`.
TENANTS_TABLE = "tenants"


def upgrade() -> None:
    """Create tables + RLS policies + app role."""
    # --- Tables ----------------------------------------------------------
    op.create_table(
        TENANTS_TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("audit_key_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{TENANTS_TABLE}.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{TENANTS_TABLE}.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(64), nullable=False, server_default="member"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # --- App role (idempotent; do not use CREATE ROLE IF NOT EXISTS,
    # which doesn't exist for non-superuser; use DO $$).)
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN;
            END IF;
        END
        $$
        """
    )
    # REVOKE BYPASSRLS explicitly — if the role somehow had it, remove it.
    op.execute(f"ALTER ROLE {APP_ROLE} NOBYPASSRLS;")

    # Grant DML on all tables + sequences to the app role.
    for tbl in (TENANTS_TABLE, *TENANT_SCOPED_TABLES):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO {APP_ROLE};")

    # --- RLS: enable + force + policy -----------------------------------
    # `tenants` — boundary by `id`.
    op.execute(f"ALTER TABLE {TENANTS_TABLE} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {TENANTS_TABLE} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_self
            ON {TENANTS_TABLE}
            USING (id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (id = current_setting('app.tenant_id')::uuid);
        """
    )

    # `departments`, `users` — boundary by `tenant_id`.
    for tbl in TENANT_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""CREATE POLICY tenant_isolation_policy
                ON {tbl}
                USING (tenant_id = current_setting('app.tenant_id')::uuid)
                WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
            """
        )


def downgrade() -> None:
    """Reverse: drop policies, disable RLS, drop tables, drop app role."""
    for tbl in TENANT_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {tbl};")
        op.execute(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")

    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_self ON {TENANTS_TABLE};")
    op.execute(f"ALTER TABLE {TENANTS_TABLE} NO FORCE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {TENANTS_TABLE} DISABLE ROW LEVEL SECURITY;")

    op.drop_table("users")
    op.drop_table("departments")
    op.drop_table(TENANTS_TABLE)

    op.execute(f"DROP ROLE IF EXISTS {APP_ROLE};")
