"""restore audit_trail table (legacy compat alongside Audit V2)

Revision ID: a7b8c9d0e1f2
Revises: c76b8fc3ef08

The Audit V2 migration (b7a2d4e91f30) dropped ``audit_trail`` while
introducing the Session/Span/Event model. But the rebuild branch still
depends on the legacy append-only write path (``PostgresAuditSink.log`` ->
``AuditEntry``) across CRUD-outside-a-Run endpoints and orchestrator steps,
and the Trace Dashboard read side (``modules/audit/service.py``) still
SELECTs from ``audit_trail``. This migration recreates the table with the
exact frozen schema + RLS + INSERT-only grant from 34cd8281e2b3 so both audit
systems run in parallel.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "c76b8fc3ef08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"
TABLE = "audit_trail"


def upgrade() -> None:
    """Recreate audit_trail table with RLS + INSERT-only grant (AD-4)."""
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ts", sa.TIMESTAMP(timezone=True), nullable=False),
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

    op.create_index("ix_audit_trail_run_id_ts", TABLE, ["run_id", "ts"])
    op.create_index("ix_audit_trail_tenant_id_ts", TABLE, ["tenant_id", "ts"])

    # --- RLS: ENABLE + FORCE + tenant isolation policy --------------------
    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_policy
            ON {TABLE}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
        """
    )

    # --- INSERT-only grant to vaic_app (append-only, AD-4) ----------------
    op.execute(f"GRANT SELECT, INSERT ON {TABLE} TO {APP_ROLE};")
    op.execute(f"REVOKE UPDATE ON {TABLE} FROM {APP_ROLE};")
    op.execute(f"REVOKE DELETE ON {TABLE} FROM {APP_ROLE};")
    op.execute(f"REVOKE TRUNCATE ON {TABLE} FROM {APP_ROLE};")


def downgrade() -> None:
    """Reverse: drop policy, disable RLS, drop table."""
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {TABLE};")
    op.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;")
    op.drop_table(TABLE)
