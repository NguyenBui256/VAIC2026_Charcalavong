"""add run status completed_with_failures (3B)

Revision ID: d5e6f7a8b9c0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-18 13:00:00.000000

Expand the workflow_runs status CHECK to allow `completed_with_failures`, a
terminal status the graph engine emits when some node failed but at least one
leaf (terminal) node still produced output -- distinguishing a failed side
branch from a total failure. Drop + recreate the CHECK (Postgres has no
in-place CHECK edit); the flat path is unaffected (still completed/failed).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_STATUSES = ("pending", "running", "awaiting_human", "completed", "failed", "timed_out")
_NEW_STATUSES = (
    "pending",
    "running",
    "awaiting_human",
    "completed",
    "completed_with_failures",
    "failed",
    "timed_out",
)


def _recreate_check(statuses: tuple[str, ...]) -> None:
    op.drop_constraint("ck_workflow_runs_status", "workflow_runs", type_="check")
    op.create_check_constraint(
        "ck_workflow_runs_status",
        "workflow_runs",
        f"status IN {statuses!r}",
    )


def upgrade() -> None:
    _recreate_check(_NEW_STATUSES)


def downgrade() -> None:
    # Fails if any run is in the new status; callers must resolve those first.
    _recreate_check(_OLD_STATUSES)
