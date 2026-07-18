"""Author (create/replace) a workflow's DAG definition (Sub-project 3D).

Distinct from `graph_snapshot.py` (which freezes the live graph INTO a run):
this reads/writes the live `workflow_nodes`/`workflow_edges`/`_approvers`
authoring tables. `assert_valid_graph` is the single DAG gate for every write.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import AuthorizationError, NotFoundError
from app.core.tenant_context import tenant_context
from app.modules.orchestrator.graph_validation import (
    GraphValidationError,
    assert_valid_graph,
)
from app.modules.orchestrator.models import (
    Workflow,
    WorkflowEdge,
    WorkflowNode,
    WorkflowNodeApprover,
)

__all__ = ["serialize_workflow_graph", "replace_workflow_graph"]


def _load_workflow(session: Session, workflow_id: uuid.UUID) -> Workflow:
    workflow = session.get(Workflow, workflow_id)
    if workflow is None:
        raise NotFoundError("Workflow not found")
    return workflow


def serialize_workflow_graph(session: Session, workflow_id: uuid.UUID) -> dict[str, Any]:
    """Read the live authored graph for the editor. Empty graph -> empty lists."""
    _load_workflow(session, workflow_id)  # RLS 404s cross-tenant
    nodes = list(
        session.execute(
            select(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id)
        ).scalars().all()
    )
    edges = list(
        session.execute(
            select(WorkflowEdge).where(WorkflowEdge.workflow_id == workflow_id)
        ).scalars().all()
    )
    node_by_id = {n.id: n for n in nodes}
    approvers = list(
        session.execute(
            select(WorkflowNodeApprover).where(
                WorkflowNodeApprover.node_id.in_([n.id for n in nodes] or [uuid.uuid4()])
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
        "edges": [
            {
                "from": node_by_id[e.from_node_id].node_key,
                "to": node_by_id[e.to_node_id].node_key,
            }
            for e in edges
            if e.from_node_id in node_by_id and e.to_node_id in node_by_id
        ],
    }


def replace_workflow_graph(
    session: Session,
    workflow_id: uuid.UUID,
    *,
    role: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate + rewrite the whole graph in one transaction; bump version.

    Requires builder role. Raises GraphValidationError (mapped to 422 by the
    route) on a malformed DAG. Edges reference node_key; stored as node ids.
    """
    if role != "builder":
        raise AuthorizationError(
            "builder role required to edit a Workflow graph", code="FORBIDDEN"
        )
    workflow = _load_workflow(session, workflow_id)
    tenant_id = tenant_context.get()

    node_keys = [n["node_key"] for n in nodes]
    edge_pairs = [(e["from"], e["to"]) for e in edges]
    assert_valid_graph(node_keys, edge_pairs)  # cycle/self-loop/dup/unknown-key
    for n in nodes:
        if not n.get("agent_id"):
            raise GraphValidationError(f"node {n['node_key']!r} has no agent")

    # Wipe existing graph for this workflow (approvers first via node ids).
    existing_ids = list(
        session.execute(
            select(WorkflowNode.id).where(WorkflowNode.workflow_id == workflow_id)
        ).scalars().all()
    )
    if existing_ids:
        session.execute(
            delete(WorkflowNodeApprover).where(
                WorkflowNodeApprover.node_id.in_(existing_ids)
            )
        )
    session.execute(delete(WorkflowEdge).where(WorkflowEdge.workflow_id == workflow_id))
    session.execute(delete(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id))

    key_to_id: dict[str, uuid.UUID] = {}
    for n in nodes:
        pos = n.get("position") or {}
        row = WorkflowNode(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            node_key=n["node_key"],
            label=n["label"],
            agent_id=uuid.UUID(str(n["agent_id"])),
            config=n.get("config") or {},
            position_x=float(pos.get("x", 0)),
            position_y=float(pos.get("y", 0)),
        )
        session.add(row)
        session.flush()  # assign row.id
        key_to_id[n["node_key"]] = row.id
        for uid in n.get("approver_user_ids") or []:
            session.add(
                WorkflowNodeApprover(
                    node_id=row.id, user_id=uuid.UUID(str(uid)), tenant_id=tenant_id
                )
            )
    for src, dst in edge_pairs:
        session.add(
            WorkflowEdge(
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                from_node_id=key_to_id[src],
                to_node_id=key_to_id[dst],
            )
        )

    workflow.version += 1
    session.commit()
    return serialize_workflow_graph(session, workflow_id)
