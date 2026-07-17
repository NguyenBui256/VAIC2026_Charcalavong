"""create audit_trail table

Revision ID: 34cd8281e2b3
Revises: ec784b72f20c
Create Date: 2026-07-17 20:27:23.723127

Story 1.5: creates the ``audit_trail`` table per PRD FR-21 + AD-4.

Schema columns (exact names per consistency-conventions.md):
    id          UUID PK (UUID v7)
    tenant_id   UUID NOT NULL (AD-2 — RLS tenant scoping)
    run_id      UUID NOT NULL
    step_id     UUID NOT NULL
    agent_id    UUID (nullable — orchestrator steps may have no agent)
    ts          timestamptz NOT NULL (UTC, millisecond precision)
    type        varchar(64) NOT NULL
    input       jsonb NOT NULL
    output      jsonb NOT NULL
    latency_ms  integer NOT NULL
    model       varchar(255) (nullable)

Append-only enforcement (AD-4):
    - RLS ENABLE + FORCE (tenant isolation, AD-2)
    - ``vaic_app`` gets INSERT only; UPDATE, DELETE, TRUNCATE all revoked
    - Even if a future GRANT accidentally adds UPDATE/DELETE, the explicit
      REVOKE in this migration removes them.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "34cd8281e2b3"
down_revision: str | Sequence[str] | None = "ec784b72f20c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"
TABLE = "audit_trail"


def upgrade() -> None:
    """Create audit_trail table with RLS + INSERT-only grant."""
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "ts",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column(
            "input",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "output",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(255), nullable=True),
    )

    # Index for common query: filter by run, ordered by time.
    op.create_index(
        "ix_audit_trail_run_id_ts",
        TABLE,
        ["run_id", "ts"],
    )
    # Index for tenant-scoped queries.
    op.create_index(
        "ix_audit_trail_tenant_id_ts",
        TABLE,
        ["tenant_id", "ts"],
    )

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

    # --- INSERT-only grant to vaic_app (AD-4 append-only) -----------------
    # Grant INSERT + SELECT (SELECT needed for RLS to work; Trace Dashboard
    # reads audit_trail in a later story, but the role needs at least SELECT
    # so RLS policies are evaluated).
    op.execute(
        f"GRANT SELECT, INSERT ON {TABLE} TO {APP_ROLE};"
    )
    # Explicitly revoke UPDATE, DELETE, TRUNCATE — append-only (AD-4).
    op.execute(f"REVOKE UPDATE ON {TABLE} FROM {APP_ROLE};")
    op.execute(f"REVOKE DELETE ON {TABLE} FROM {APP_ROLE};")
    op.execute(f"REVOKE TRUNCATE ON {TABLE} FROM {APP_ROLE};")


def downgrade() -> None:
    """Reverse: drop policy, disable RLS, drop table."""
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {TABLE};")
    op.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;")
    op.drop_table(TABLE)
