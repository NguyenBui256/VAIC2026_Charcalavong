"""GRANT DELETE on graph authoring tables to vaic_app (3D)

The 3D whole-graph replace (`replace_workflow_graph`) rewrites a workflow's
DAG by deleting the existing nodes/edges/approvers and re-inserting them in one
transaction. The original graph-tables migration (c3d4e5f6a7b8) granted only
SELECT/INSERT/UPDATE, so the app role could not DELETE — the PUT
/workflows/{id}/graph-definition raised "permission denied for table
workflow_edges". This grants DELETE on the three authoring tables.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-07-18 22:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f7a8b9c0d1e2"
down_revision: str | Sequence[str] | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"

# Authoring tables the whole-graph replace deletes from (approvers -> edges ->
# nodes ordering is handled in the domain layer; CASCADE FKs cover the rest).
_AUTHORING_TABLES = (
    "workflow_nodes",
    "workflow_edges",
    "workflow_node_approvers",
)


def upgrade() -> None:
    for table in _AUTHORING_TABLES:
        op.execute(f"GRANT DELETE ON {table} TO {APP_ROLE};")


def downgrade() -> None:
    for table in _AUTHORING_TABLES:
        op.execute(f"REVOKE DELETE ON {table} FROM {APP_ROLE};")
