"""action_bindings: add target_type + agent_id; workflow_id becomes nullable.

Lets a binding target EITHER a workflow (existing) OR a single agent (new).
Backfills existing rows to target_type='workflow'. CHECK enforces exactly one
target matching the discriminator. No new RLS policy needed (column adds on an
already-RLS table).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ad30agenttarget01"
down_revision: str | Sequence[str] | None = "ac20actions01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "action_bindings",
        sa.Column("target_type", sa.String(16), nullable=False, server_default="workflow"),
    )
    op.add_column(
        "action_bindings",
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    # Existing rows all targeted a workflow — backfill is implicit via the
    # server_default; make workflow_id nullable now that agent_id can carry it.
    op.alter_column("action_bindings", "workflow_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.create_check_constraint(
        "ck_action_bindings_target",
        "action_bindings",
        "(target_type = 'workflow' AND workflow_id IS NOT NULL AND agent_id IS NULL) "
        "OR (target_type = 'agent' AND agent_id IS NOT NULL AND workflow_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_action_bindings_target", "action_bindings", type_="check")
    op.alter_column("action_bindings", "workflow_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.drop_column("action_bindings", "agent_id")
    op.drop_column("action_bindings", "target_type")
