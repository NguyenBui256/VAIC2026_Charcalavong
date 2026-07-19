"""create run_rollback_requests table (3B)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-18 12:00:00.000000

Adds the reject->rollback request table with tenant-scoped RLS.
Node/run status CHECK constraints are unchanged (an in-flight rollback is
signalled by a pending row here, not a new node status).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"

ROLLBACK_STATUSES = ("pending", "accepted", "refused")


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_policy
            ON {table}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
        """
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE ON {table} TO {APP_ROLE};")


def _disable_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def upgrade() -> None:
    op.create_table(
        "run_rollback_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requester_node_key", sa.String(64), nullable=False),
        sa.Column("target_node_key", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "decided_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"status IN {ROLLBACK_STATUSES!r}",
            name="ck_run_rollback_requests_status",
        ),
    )
    op.create_index(
        "ix_run_rollback_requests_tenant_id",
        "run_rollback_requests",
        ["tenant_id"],
    )
    op.create_index(
        "ix_run_rollback_requests_run_id",
        "run_rollback_requests",
        ["run_id"],
    )
    op.create_index(
        "ix_run_rollback_requests_status",
        "run_rollback_requests",
        ["status"],
    )
    _enable_rls("run_rollback_requests")


def downgrade() -> None:
    _disable_rls("run_rollback_requests")
    op.drop_table("run_rollback_requests")
