"""create graph workflow tables (3A)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-18 09:00:00.000000

Sub-project 3A: builder-authored DAG workflow data model. Definition tables
(workflow_nodes / workflow_edges / workflow_node_approvers) + per-run runtime
state (run_node_executions) + a graph_snapshot column on workflow_runs.
Mirrors the RLS + grant DDL pattern of 39dfa51cec0c (workflow_runs/tasks).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"

NODE_EXECUTION_STATUSES = (
    "pending",
    "running",
    "awaiting_approval",
    "completed",
    "failed",
    "rejected",
    "skipped",
    "rolled_back",
)


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
    op.add_column(
        "workflow_runs",
        sa.Column("graph_snapshot", postgresql.JSONB(), nullable=True),
    )

    op.create_table(
        "workflow_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_key", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("position_x", sa.Float(), nullable=False, server_default="0"),
        sa.Column("position_y", sa.Float(), nullable=False, server_default="0"),
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
        sa.UniqueConstraint("workflow_id", "node_key", name="uq_workflow_nodes_key"),
    )
    op.create_index("ix_workflow_nodes_tenant_id", "workflow_nodes", ["tenant_id"])
    op.create_index("ix_workflow_nodes_workflow_id", "workflow_nodes", ["workflow_id"])

    op.create_table(
        "workflow_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "from_node_id", "to_node_id", name="uq_workflow_edges_pair"
        ),
    )
    op.create_index("ix_workflow_edges_tenant_id", "workflow_edges", ["tenant_id"])
    op.create_index("ix_workflow_edges_workflow_id", "workflow_edges", ["workflow_id"])

    op.create_table(
        "workflow_node_approvers",
        sa.Column(
            "node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_nodes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_workflow_node_approvers_tenant_id",
        "workflow_node_approvers",
        ["tenant_id"],
    )
    op.create_index(
        "ix_workflow_node_approvers_user_id", "workflow_node_approvers", ["user_id"]
    )

    op.create_table(
        "run_node_executions",
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
        sa.Column("node_key", sa.String(64), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="pending"
        ),
        sa.Column("input", postgresql.JSONB(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column(
            "approver_user_ids",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("decision", sa.String(16), nullable=True),
        sa.Column(
            "decided_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("guidance", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"status IN {NODE_EXECUTION_STATUSES!r}",
            name="ck_run_node_executions_status",
        ),
        sa.UniqueConstraint("run_id", "node_key", name="uq_run_node_executions_key"),
    )
    op.create_index(
        "ix_run_node_executions_tenant_id", "run_node_executions", ["tenant_id"]
    )
    op.create_index(
        "ix_run_node_executions_run_id", "run_node_executions", ["run_id"]
    )
    op.create_index(
        "ix_run_node_executions_status", "run_node_executions", ["status"]
    )

    _enable_rls("workflow_nodes")
    _enable_rls("workflow_edges")
    _enable_rls("workflow_node_approvers")
    _enable_rls("run_node_executions")


def downgrade() -> None:
    _disable_rls("run_node_executions")
    _disable_rls("workflow_node_approvers")
    _disable_rls("workflow_edges")
    _disable_rls("workflow_nodes")
    op.drop_table("run_node_executions")
    op.drop_table("workflow_node_approvers")
    op.drop_table("workflow_edges")
    op.drop_table("workflow_nodes")
    op.drop_column("workflow_runs", "graph_snapshot")
