"""Human-review decision + rollback service for graph runs (Sub-project 3B).

Pure service layer (no HTTP). Each decision mutates `run_node_executions` /
`run_rollback_requests` via CAS and the caller (graph_routes) re-enqueues
`run_workflow(resume=True)`.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.ids import uuid7
from app.modules.orchestrator.graph_engine import load_graph
from app.modules.orchestrator.graph_serialization import serialize_run_node_execution
from app.modules.orchestrator.graph_validation import descendants, parents_by_key
from app.modules.orchestrator.models import (
    RunNodeExecution,
    RunRollbackRequest,
    WorkflowRun,
)
from app.modules.orchestrator.service import _audit, _reassert_rls
from app.modules.orchestrator.state import transition_node_status

_VALID_ACTIONS = ("approve", "retry", "override", "reject")


class ReviewError(Exception):
    """Service-level error with an HTTP status hint."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _load_run(session: Session, run_id: uuid.UUID | str) -> WorkflowRun:
    run = session.get(WorkflowRun, uuid.UUID(str(run_id)))
    if run is None:
        raise ReviewError(404, "run not found")
    return run


def _get_node(
    session: Session, run_id: uuid.UUID | str, node_key: str
) -> RunNodeExecution:
    row = (
        session.query(RunNodeExecution)
        .filter(
            RunNodeExecution.run_id == uuid.UUID(str(run_id)),
            RunNodeExecution.node_key == node_key,
        )
        # Session uses expire_on_commit=False and mutations here are raw-SQL
        # CAS commits that never expire the identity map, so without this the
        # row would come back stale after a decision commits (mirrors
        # graph_engine._load_node_execs).
        .execution_options(populate_existing=True)
        .first()
    )
    if row is None:
        raise ReviewError(404, f"node {node_key} not found")
    return row


def _require_approver(row_or_keys: Any, actor_user_id: uuid.UUID | str) -> None:
    approvers = (
        row_or_keys.approver_user_ids
        if hasattr(row_or_keys, "approver_user_ids")
        else row_or_keys
    ) or []
    if str(actor_user_id) not in [str(a) for a in approvers]:
        raise ReviewError(403, "caller is not an approver of this node")


def _audit_decision(
    session: Session, run_id: uuid.UUID | str, node_key: str, action: str, actor: Any
) -> None:
    _reassert_rls(session)
    _audit(
        session,
        dict(
            run_id=str(run_id),
            step_id=str(uuid7()),
            agent_id="",
            type=f"graph_node.{action}",
            input={"node_key": node_key, "actor": str(actor)},
            output={},
            latency_ms=0,
        ),
    )


# --- node decisions ----------------------------------------------------------


def record_decision(
    session: Session,
    run_id: uuid.UUID | str,
    node_key: str,
    *,
    action: str,
    actor_user_id: uuid.UUID | str,
    guidance: str | None = None,
    output: dict[str, Any] | None = None,
    reason: str | None = None,
    target_node_key: str | None = None,
) -> dict[str, Any]:
    if action not in _VALID_ACTIONS:
        raise ReviewError(400, f"invalid action: {action}")
    row = _get_node(session, run_id, node_key)
    if row.status != "awaiting_approval":
        raise ReviewError(409, "node is not awaiting a decision")
    _require_approver(row, actor_user_id)

    common = {"decided_by": str(actor_user_id), "decided_at": _now_sql_marker()}

    if action == "approve":
        _cas_or_conflict(
            session, row.id, "awaiting_approval", "completed",
            {**common, "decision": "approve"},
        )
    elif action == "retry":
        _cas_or_conflict(
            session, row.id, "awaiting_approval", "pending",
            {**common, "decision": "retry", "guidance": guidance},
        )
    elif action == "override":
        _cas_or_conflict(
            session, row.id, "awaiting_approval", "completed",
            {**common, "decision": "override", "output": json.dumps(output or {})},
        )
    else:  # reject
        return _do_reject(
            session, run_id, row, actor_user_id, reason, target_node_key
        )

    _audit_decision(session, run_id, node_key, action, actor_user_id)
    _reassert_rls(session)
    return serialize_run_node_execution(_get_node(session, run_id, node_key))


def _now_sql_marker() -> Any:
    # decided_at is stamped by SQL now() via a dedicated UPDATE below; the
    # CAS helper writes plain params, so we set decided_at through text().
    return None


def _cas_or_conflict(
    session: Session,
    node_id: uuid.UUID,
    from_status: str,
    to_status: str,
    extra_cols: dict[str, Any],
) -> None:
    # Drop the decided_at sentinel; stamp it via a follow-up now() update.
    cols = {k: v for k, v in extra_cols.items() if v is not None or k == "guidance"}
    cols.pop("decided_at", None)
    _reassert_rls(session)
    won = transition_node_status(
        session,
        node_id,
        from_status=from_status,
        to_status=to_status,
        extra_cols=cols,
        extra_where="decision IS NULL",
    )
    if not won:
        raise ReviewError(409, "node already decided")
    _reassert_rls(session)
    session.execute(
        text("UPDATE run_node_executions SET decided_at=now() WHERE id=:id"),
        {"id": str(node_id)},
    )
    session.commit()
    _reassert_rls(session)


def _do_reject(
    session: Session,
    run_id: uuid.UUID | str,
    row: RunNodeExecution,
    actor_user_id: uuid.UUID | str,
    reason: str | None,
    target_node_key: str | None,
) -> dict[str, Any]:
    run = _load_run(session, run_id)
    node_keys, _nodes_by_key, edges = load_graph(run.graph_snapshot)
    parents = parents_by_key(node_keys, edges)
    if not target_node_key or target_node_key not in parents.get(row.node_key, []):
        raise ReviewError(400, "target_node_key must be a parent of the node")

    # First-wins on reject: node stays awaiting_approval, but decision must be NULL.
    _reassert_rls(session)
    won = transition_node_status(
        session,
        row.id,
        from_status="awaiting_approval",
        to_status="awaiting_approval",
        extra_cols={"decision": "reject", "reason": reason, "decided_by": str(actor_user_id)},
        extra_where="decision IS NULL",
    )
    if not won:
        raise ReviewError(409, "node already decided")
    _reassert_rls(session)
    session.execute(
        text("UPDATE run_node_executions SET decided_at=now() WHERE id=:id"),
        {"id": str(row.id)},
    )
    session.commit()

    _reassert_rls(session)
    req = RunRollbackRequest(
        id=uuid7(),
        tenant_id=row.tenant_id,
        run_id=uuid.UUID(str(run_id)),
        requester_node_key=row.node_key,
        target_node_key=target_node_key,
        reason=reason,
        status="pending",
    )
    session.add(req)
    session.commit()
    _audit_decision(session, run_id, row.node_key, "reject", actor_user_id)

    # Auto target parent (no approvers) -> auto-accept inline.
    _reassert_rls(session)
    target_row = _get_node(session, run_id, target_node_key)
    if not (target_row.approver_user_ids or []):
        _reassert_rls(session)
        _accept_rollback(session, run_id, req, decided_by=None)

    _reassert_rls(session)
    return serialize_run_node_execution(_get_node(session, run_id, row.node_key))


# --- rollback confirm --------------------------------------------------------


def confirm_rollback(
    session: Session,
    run_id: uuid.UUID | str,
    rollback_id: uuid.UUID | str,
    *,
    accept: bool,
    actor_user_id: uuid.UUID | str,
    refuse_reason: str | None = None,
) -> dict[str, Any]:
    req = session.get(RunRollbackRequest, uuid.UUID(str(rollback_id)))
    if req is None or str(req.run_id) != str(run_id):
        raise ReviewError(404, "rollback request not found")
    if req.status != "pending":
        raise ReviewError(409, "rollback already resolved")
    target_row = _get_node(session, run_id, req.target_node_key)
    _require_approver(target_row, actor_user_id)

    if accept:
        _accept_rollback(session, run_id, req, decided_by=actor_user_id)
    else:
        _refuse_rollback(
            session, run_id, req, decided_by=actor_user_id, refuse_reason=refuse_reason
        )
    _reassert_rls(session)
    return {"id": str(req.id), "status": "accepted" if accept else "refused"}


def _reset_node_to_pending(
    session: Session, node_id: uuid.UUID, *, guidance: str | None = None
) -> None:
    session.execute(
        text(
            """UPDATE run_node_executions
               SET status='pending', output=NULL, decision=NULL, decided_by=NULL,
                   reason=NULL, guidance=:guidance, decided_at=NULL,
                   started_at=NULL, completed_at=NULL, input=NULL
               WHERE id=:id"""
        ),
        {"id": str(node_id), "guidance": guidance},
    )
    session.commit()


def _accept_rollback(
    session: Session,
    run_id: uuid.UUID | str,
    req: RunRollbackRequest,
    *,
    decided_by: uuid.UUID | str | None,
) -> None:
    _reassert_rls(session)
    session.execute(
        text(
            "UPDATE run_rollback_requests SET status='accepted', decided_by=:by, "
            "decided_at=now() WHERE id=:id"
        ),
        {"by": str(decided_by) if decided_by else None, "id": str(req.id)},
    )
    session.commit()

    _reassert_rls(session)
    run = _load_run(session, run_id)
    node_keys, _nodes_by_key, edges = load_graph(run.graph_snapshot)
    desc = descendants(node_keys, edges, req.target_node_key)

    # Mark the whole descendant subtree rolled_back, then pending (spec 5.3).
    for key in desc:
        node = _get_node(session, run_id, key)
        session.execute(
            text("UPDATE run_node_executions SET status='rolled_back' WHERE id=:id"),
            {"id": str(node.id)},
        )
    session.commit()
    _reassert_rls(session)
    for key in desc:
        node = _get_node(session, run_id, key)
        _reset_node_to_pending(session, node.id)
        _reassert_rls(session)

    # Reset the target itself -> pending with the reject reason as guidance.
    target = _get_node(session, run_id, req.target_node_key)
    _reset_node_to_pending(session, target.id, guidance=req.reason)
    _reassert_rls(session)
    _audit(
        session,
        dict(
            run_id=str(run_id),
            step_id=str(uuid7()),
            agent_id="",
            type="graph_rollback.accepted",
            input={"target": req.target_node_key, "requester": req.requester_node_key},
            output={"descendants": sorted(desc)},
            latency_ms=0,
        ),
    )
    _reassert_rls(session)


def _refuse_rollback(
    session: Session,
    run_id: uuid.UUID | str,
    req: RunRollbackRequest,
    *,
    decided_by: uuid.UUID | str,
    refuse_reason: str | None = None,
) -> None:
    _reassert_rls(session)
    session.execute(
        text(
            "UPDATE run_rollback_requests SET status='refused', decided_by=:by, "
            "refuse_reason=:refuse_reason, decided_at=now() WHERE id=:id"
        ),
        {"by": str(decided_by), "refuse_reason": refuse_reason, "id": str(req.id)},
    )
    session.commit()
    # Return the rejecting node to a fresh awaiting_approval decision state:
    # clear its reject decision so it can be Approve/Retry/Override'd again.
    _reassert_rls(session)
    node = _get_node(session, run_id, req.requester_node_key)
    session.execute(
        text(
            "UPDATE run_node_executions SET decision=NULL, decided_by=NULL, "
            "reason=NULL, decided_at=NULL WHERE id=:id"
        ),
        {"id": str(node.id)},
    )
    session.commit()
    _reassert_rls(session)
    _audit(
        session,
        dict(
            run_id=str(run_id),
            step_id=str(uuid7()),
            agent_id="",
            type="graph_rollback.refused",
            input={"target": req.target_node_key, "requester": req.requester_node_key},
            output={},
            latency_ms=0,
        ),
    )
    _reassert_rls(session)


# --- read model --------------------------------------------------------------


def list_run_nodes(session: Session, run_id: uuid.UUID | str) -> dict[str, Any]:
    _reassert_rls(session)
    rows = (
        session.query(RunNodeExecution)
        .filter(RunNodeExecution.run_id == uuid.UUID(str(run_id)))
        .execution_options(populate_existing=True)
        .all()
    )
    reqs = (
        session.query(RunRollbackRequest)
        .filter(RunRollbackRequest.run_id == uuid.UUID(str(run_id)))
        .execution_options(populate_existing=True)
        .all()
    )

    def _ser_req(r: RunRollbackRequest) -> dict[str, Any]:
        return {
            "id": str(r.id),
            "requester_node_key": r.requester_node_key,
            "target_node_key": r.target_node_key,
            "reason": r.reason,
            "refuse_reason": r.refuse_reason,
            "status": r.status,
        }

    return {
        "nodes": [serialize_run_node_execution(r) for r in rows],
        "rollbacks": {
            "pending": [_ser_req(r) for r in reqs if r.status == "pending"],
            "refused": [_ser_req(r) for r in reqs if r.status == "refused"],
        },
    }
