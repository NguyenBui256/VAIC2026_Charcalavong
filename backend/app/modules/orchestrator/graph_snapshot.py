"""Snapshot the live workflow graph into a Run at creation time (3A).

`build_graph_snapshot` reads the current nodes/edges/approvers (RLS-scoped)
and returns the immutable JSON shape stored on `WorkflowRun.graph_snapshot`;
`create_run_node_executions` materializes one `pending` runtime row per node.
Returns `None` when the workflow has no graph -- the caller then falls back
to the legacy flat run path unchanged.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.orchestrator.graph_validation import assert_valid_graph
from app.modules.orchestrator.models import (
    RunNodeExecution,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeApprover,
    WorkflowRun,
)

__all__ = ["build_graph_snapshot", "create_run_node_executions"]


def build_graph_snapshot(session: Session, workflow_id: uuid.UUID) -> dict | None:
    """Read the live graph for `workflow_id`; return the snapshot dict or None.

    None means "no graph" (zero nodes) -- the legacy flat path applies. A
    non-empty graph is validated (`assert_valid_graph`) before snapshotting so
    a corrupt definition fails loudly at run creation, not mid-execution.
    """
    nodes = list(
        session.execute(
            select(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id)
        ).scalars().all()
    )
    if not nodes:
        return None

    edges = list(
        session.execute(
            select(WorkflowEdge).where(WorkflowEdge.workflow_id == workflow_id)
        ).scalars().all()
    )
    node_by_id = {n.id: n for n in nodes}
    edge_key_pairs = [
        (node_by_id[e.from_node_id].node_key, node_by_id[e.to_node_id].node_key)
        for e in edges
        if e.from_node_id in node_by_id and e.to_node_id in node_by_id
    ]
    assert_valid_graph([n.node_key for n in nodes], edge_key_pairs)

    approvers = list(
        session.execute(
            select(WorkflowNodeApprover).where(
                WorkflowNodeApprover.node_id.in_([n.id for n in nodes])
            )
        ).scalars().all()
    )
    approvers_by_node: dict[uuid.UUID, list[str]] = {}
    for a in approvers:
        approvers_by_node.setdefault(a.node_id, []).append(str(a.user_id))

    return {
        "nodes": [
            {
                "node_key": n.node_key,
                "label": n.label,
                "agent_id": str(n.agent_id),
                "config": n.config or {},
                "position": {"x": n.position_x, "y": n.position_y},
                "approver_user_ids": approvers_by_node.get(n.id, []),
            }
            for n in nodes
        ],
        "edges": [{"from": src, "to": dst} for src, dst in edge_key_pairs],
    }


def create_run_node_executions(
    session: Session, run: WorkflowRun, snapshot: dict
) -> list[RunNodeExecution]:
    """Materialize one `pending` RunNodeExecution per node in the snapshot."""
    rows = [
        RunNodeExecution(
            tenant_id=run.tenant_id,
            run_id=run.id,
            node_key=node["node_key"],
            agent_id=uuid.UUID(node["agent_id"]),
            status="pending",
            approver_user_ids=node.get("approver_user_ids", []),
        )
        for node in snapshot["nodes"]
    ]
    session.add_all(rows)
    return rows
