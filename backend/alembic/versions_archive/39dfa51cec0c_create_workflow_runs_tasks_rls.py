"""create workflow_runs + tasks rls

Revision ID: 39dfa51cec0c
Revises: 1ad51bb8e8cb
Create Date: 2026-07-18 04:40:00.000000

Story 3.2: creates `workflow_runs` + `tasks` — Epic 3's second migration.
Mirrors the RLS + grant DDL pattern of `82478b8e9fea_create_tools_rls.py`
/ `1ad51bb8e8cb_create_workflows_rls.py`.

Schema columns (`workflow_runs`):
    id            UUID PK (UUID v7, generated app-side)
    tenant_id     UUID NOT NULL FK tenants.id ON DELETE CASCADE
    workflow_id   UUID NOT NULL FK workflows.id ON DELETE RESTRICT
    status        varchar(32) NOT NULL DEFAULT 'pending'
                  CHECK IN (pending, running, awaiting_human, completed,
                            failed, timed_out)                    (AC7)
    input         jsonb NOT NULL DEFAULT '{}'
    result        jsonb NULL
    started_at    timestamptz NULL
    ended_at      timestamptz NULL
    created_at    timestamptz NOT NULL DEFAULT now()

Schema columns (`tasks`):
    id                UUID PK (UUID v7, generated app-side)
    tenant_id         UUID NOT NULL FK tenants.id ON DELETE CASCADE
    run_id            UUID NOT NULL FK workflow_runs.id ON DELETE CASCADE
    target_agent_id   UUID NOT NULL FK agents.id ON DELETE RESTRICT
    status            varchar(32) NOT NULL DEFAULT 'pending'
                      CHECK IN (pending, claimed, completed, failed) (AC7)
    schema_payload    jsonb NOT NULL
    result            jsonb NULL
    claimed_at        timestamptz NULL
    completed_at      timestamptz NULL
    created_at        timestamptz NOT NULL DEFAULT now()

Indexes: `ix_workflow_runs_tenant_id`, `ix_workflow_runs_status` (startup
poller's `WHERE status='running'` scan), `ix_tasks_tenant_id`,
`ix_tasks_run_id`, `ix_tasks_status_target_agent` (composite, Story 3.4's
claim-poll query).

RLS (AD-2): ENABLE + FORCE + tenant_isolation_policy on BOTH tables.
Grants: SELECT, INSERT, UPDATE only (UPDATE required for CAS transitions,
AD-6; no DELETE AC exists for either table).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "39dfa51cec0c"
down_revision: str | Sequence[str] | None = "1ad51bb8e8cb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"

RUN_STATUSES = ("pending", "running", "awaiting_human", "completed", "failed", "timed_out")
TASK_STATUSES = ("pending", "claimed", "completed", "failed")


def _enable_rls(table: str) -> None:
    """ENABLE + FORCE RLS and create the standard tenant_isolation_policy."""
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
    """Create workflow_runs + tasks with RLS + CRUD-only grants (AC1, AC7)."""
    op.create_table(
        "workflow_runs",
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
            sa.ForeignKey("workflows.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="pending"
        ),
        sa.Column("input", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"status IN {RUN_STATUSES!r}", name="ck_workflow_runs_status"
        ),
    )
    op.create_index("ix_workflow_runs_tenant_id", "workflow_runs", ["tenant_id"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])

    op.create_table(
        "tasks",
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
        sa.Column(
            "target_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(32), nullable=False, server_default="pending"
        ),
        sa.Column("schema_payload", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("claimed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(f"status IN {TASK_STATUSES!r}", name="ck_tasks_status"),
    )
    op.create_index("ix_tasks_tenant_id", "tasks", ["tenant_id"])
    op.create_index("ix_tasks_run_id", "tasks", ["run_id"])
    op.create_index(
        "ix_tasks_status_target_agent", "tasks", ["status", "target_agent_id"]
    )

    # --- RLS: ENABLE + FORCE + policy + grants (both tables) ---------------
    _enable_rls("workflow_runs")
    _enable_rls("tasks")


def downgrade() -> None:
    """Reverse: drop policies, disable RLS, drop tables (tasks before
    workflow_runs — FK order)."""
    _disable_rls("tasks")
    _disable_rls("workflow_runs")
    op.drop_table("tasks")
    op.drop_table("workflow_runs")
