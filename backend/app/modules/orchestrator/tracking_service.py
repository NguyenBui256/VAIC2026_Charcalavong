"""Cross-run, per-user review inbox read model (Tracking).

Pure service layer (no HTTP). Aggregates run_node_executions the current user
is an approver on into one row per run, with a "my turn" flag. Reuses the
RLS-scoped session — the explicit user_id predicate scopes to the caller's
own inbox.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.orchestrator.graph_engine import load_graph
from app.modules.orchestrator.models import RunNodeExecution, WorkflowRun
from app.modules.orchestrator.service import _reassert_rls

_TERMINAL_RUN_STATUSES = (
    "completed",
    "failed",
    "timed_out",
    "completed_with_failures",
)


def _iso(dt: Any) -> str | None:
    return dt.isoformat() if dt is not None else None


def _label_for(snapshot: dict[str, Any] | None, node_key: str) -> str:
    if not snapshot:
        return node_key
    try:
        _keys, nodes_by_key, _edges = load_graph(snapshot)
    except Exception:
        return node_key
    return nodes_by_key.get(node_key, {}).get("label", node_key)


def _run_ids_for_approver(session: Session, user_id: uuid.UUID) -> list[str]:
    """Distinct run ids that have >=1 node exec where user is an approver."""
    _reassert_rls(session)
    uid_json = json.dumps([str(user_id)])
    rows = session.execute(
        text(
            "SELECT DISTINCT run_id FROM run_node_executions "
            "WHERE approver_user_ids @> CAST(:uid AS jsonb)"
        ),
        {"uid": uid_json},
    ).fetchall()
    return [str(r[0]) for r in rows]


def _build_item(
    session: Session, user_id: uuid.UUID, run: WorkflowRun
) -> dict[str, Any]:
    _reassert_rls(session)
    execs: list[RunNodeExecution] = (
        session.query(RunNodeExecution)
        .filter(RunNodeExecution.run_id == run.id)
        .execution_options(populate_existing=True)
        .all()
    )
    uid = str(user_id)

    my_awaiting: list[dict[str, str]] = []
    latest = run.started_at or run.created_at
    for e in execs:
        approvers = [str(a) for a in (e.approver_user_ids or [])]
        for ts in (e.decided_at, e.completed_at, e.started_at, e.created_at):
            if ts is not None and (latest is None or ts > latest):
                latest = ts
        if (
            e.status == "awaiting_approval"
            and e.decision is None
            and uid in approvers
        ):
            label = _label_for(run.graph_snapshot, e.node_key)
            my_awaiting.append({"node_key": e.node_key, "label": label})

    # "current" = the node the run is actively on, by strict priority:
    # awaiting_approval > running > pending. Deterministic node_key tie-break
    # so identical data always yields the same node.
    def _pick(status: str) -> dict[str, str] | None:
        matches = sorted(
            (e for e in execs if e.status == status), key=lambda e: e.node_key
        )
        if not matches:
            return None
        e = matches[0]
        return {
            "node_key": e.node_key,
            "label": _label_for(run.graph_snapshot, e.node_key),
            "status": e.status,
        }

    current: dict[str, str] | None = (
        _pick("awaiting_approval") or _pick("running") or _pick("pending")
    )

    # Look up workflow name (RLS-scoped).
    _reassert_rls(session)
    name_row = session.execute(
        text("SELECT name FROM workflows WHERE id = :wid"),
        {"wid": str(run.workflow_id)},
    ).fetchone()

    return {
        "run_id": str(run.id),
        "workflow_id": str(run.workflow_id),
        "workflow_name": name_row[0] if name_row else "",
        "run_status": run.status,
        "my_awaiting_nodes": my_awaiting,
        "current_node": current,
        "is_my_turn": bool(my_awaiting),
        "updated_at": _iso(latest),
    }


def list_my_tracking(
    session: Session, user_id: uuid.UUID, *, scope: str = "active"
) -> list[dict[str, Any]]:
    run_ids = _run_ids_for_approver(session, user_id)
    items: list[dict[str, Any]] = []
    for rid in run_ids:
        _reassert_rls(session)
        run = session.get(WorkflowRun, uuid.UUID(rid))
        if run is None:
            continue
        if scope == "active" and run.status in _TERMINAL_RUN_STATUSES:
            continue
        items.append(_build_item(session, user_id, run))
    # Sort: my-turn first, then most-recently-updated.
    items.sort(
        key=lambda it: (it["is_my_turn"], it["updated_at"] or ""),
        reverse=True,
    )
    return items


def count_my_awaiting(session: Session, user_id: uuid.UUID) -> int:
    return sum(
        1 for it in list_my_tracking(session, user_id, scope="active") if it["is_my_turn"]
    )
