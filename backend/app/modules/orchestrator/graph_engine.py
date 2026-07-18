"""Graph workflow execution engine (Sub-project 3B).

Walks a run's immutable `graph_snapshot` in topological order, resolving each
node's input from its parents' outputs, dispatching the node's agent, and
pausing the whole run at human-gated nodes. Fully state-driven: everything is
recomputed from `run_node_executions` + `graph_snapshot` on each (re)entry, so
`graph_orchestrate` is safe to re-run on the `resume=True` path.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.ids import uuid7
from app.modules.agent_builder.agent_executor import AgentExecutor, get_agent
from app.modules.orchestrator.graph_validation import (
    parents_by_key,
    topological_order,
)
from app.modules.orchestrator.models import RunNodeExecution, WorkflowRun
from app.modules.orchestrator.service import _audit, _reassert_rls
from app.modules.orchestrator.state import (
    transition_and_audit,
    transition_node_status,
)


def load_graph(
    snapshot: dict[str, Any],
) -> tuple[list[str], dict[str, dict[str, Any]], list[tuple[str, str]]]:
    """Parse a stored snapshot into (node_keys, nodes_by_key, edges)."""
    node_keys = [n["node_key"] for n in snapshot["nodes"]]
    nodes_by_key = {n["node_key"]: n for n in snapshot["nodes"]}
    edges = [(e["from"], e["to"]) for e in snapshot["edges"]]
    return node_keys, nodes_by_key, edges


def _load_run(session: Session, run_id: uuid.UUID | str) -> WorkflowRun:
    run = session.get(WorkflowRun, uuid.UUID(str(run_id)))
    if run is None:
        raise RuntimeError(f"graph_orchestrate: run {run_id} not found")
    return run


def _load_node_execs(
    session: Session, run_id: uuid.UUID | str
) -> dict[str, RunNodeExecution]:
    rows = (
        session.query(RunNodeExecution)
        .filter(RunNodeExecution.run_id == uuid.UUID(str(run_id)))
        .all()
    )
    return {r.node_key: r for r in rows}


def _has_pending_rollback(session: Session, run_id: uuid.UUID | str) -> bool:
    from app.modules.orchestrator.models import RunRollbackRequest

    return (
        session.query(RunRollbackRequest)
        .filter(
            RunRollbackRequest.run_id == uuid.UUID(str(run_id)),
            RunRollbackRequest.status == "pending",
        )
        .first()
        is not None
    )


def _set_run_awaiting_human(session: Session, run_id: uuid.UUID | str) -> None:
    _reassert_rls(session)
    transition_and_audit(
        session,
        kind="run",
        entity_id=run_id,
        run_id=run_id,
        from_status="running",
        to_status="awaiting_human",
    )
    _reassert_rls(session)


def _build_node_payload(
    node: dict[str, Any], resolved_input: dict[str, Any], guidance: str | None
) -> dict[str, Any]:
    """Reuse the flat path's TaskSchemaModel shape (open question resolved)."""
    summary = node.get("label", "") or ""
    if guidance:
        summary = f"{summary}\n\nReviewer guidance: {guidance}"
    return {
        "task": {"summary": summary},
        "target_agent_id": node["agent_id"],
        "input": resolved_input,
        "output": {},
        "expected": [],
        "criteria": node.get("config", {}) or {},
    }


def _node_department(session: Session, agent_id: uuid.UUID | str) -> uuid.UUID:
    return get_agent(session, agent_id).department_id


async def run_node(
    session: Session,
    run: WorkflowRun,
    row: RunNodeExecution,
    node: dict[str, Any],
    parent_keys: list[str],
    execs: dict[str, RunNodeExecution],
    *,
    executor: Any | None = None,
) -> Any:
    """CAS pending->running, resolve input, dispatch the agent.

    Returns the `TaskExecutionResult` on success, or None if the node was
    marked `failed` (infra error) or the pending->running CAS was lost.
    """
    resolved_input: dict[str, Any] = (
        dict(run.input or {})
        if not parent_keys
        else {p: execs[p].output for p in parent_keys}
    )
    _reassert_rls(session)
    won = transition_node_status(
        session,
        row.id,
        from_status="pending",
        to_status="running",
        extra_cols={"input": json.dumps(resolved_input)},
    )
    if not won:
        return None
    _reassert_rls(session)
    payload = _build_node_payload(node, resolved_input, row.guidance)
    executor = executor or AgentExecutor(session)
    dept_id = _node_department(session, row.agent_id)
    try:
        return await executor.execute_task(
            row.agent_id,
            payload,
            tenant_id=row.tenant_id,
            department_id=dept_id,
        )
    except Exception as exc:  # infra error -> node fails, run finalizes failed
        _reassert_rls(session)
        transition_node_status(
            session, row.id, from_status="running", to_status="failed"
        )
        _reassert_rls(session)
        _audit(
            session,
            dict(
                run_id=str(run.id),
                step_id=str(uuid7()),
                agent_id=str(row.agent_id),
                type="graph_node.failed",
                input={"node_key": row.node_key},
                output={"error": str(exc)},
                latency_ms=0,
            ),
        )
        return None


def finalize_run(session: Session, run_id: uuid.UUID | str, node_keys: list[str]) -> None:
    """Aggregate node outputs into run.result; CAS running->completed/failed."""
    _reassert_rls(session)
    execs = _load_node_execs(session, run_id)
    result = {k: execs[k].output for k in node_keys if k in execs}
    any_failed = any(execs[k].status == "failed" for k in node_keys if k in execs)
    to_status = "failed" if any_failed else "completed"
    _reassert_rls(session)
    transition_and_audit(
        session,
        kind="run",
        entity_id=run_id,
        run_id=run_id,
        from_status="running",
        to_status=to_status,
        extra_cols={"result": json.dumps(result)},
    )
    _reassert_rls(session)


async def graph_orchestrate(
    session: Session, run_id: uuid.UUID | str, *, executor: Any | None = None
) -> None:
    """Engine entrypoint. Re-enterable; recomputes state each call."""
    _reassert_rls(session)
    run = _load_run(session, run_id)
    snapshot = run.graph_snapshot
    node_keys, nodes_by_key, edges = load_graph(snapshot)
    parents = parents_by_key(node_keys, edges)
    order = topological_order(node_keys, edges)

    while True:
        _reassert_rls(session)
        run = _load_run(session, run_id)
        execs = _load_node_execs(session, run_id)

        # Guard 1: a pending rollback blocks all forward progress.
        if _has_pending_rollback(session, run_id):
            _set_run_awaiting_human(session, run_id)
            return

        # Guard 2: a node awaiting a human decision -> pause.
        if any(r.status == "awaiting_approval" for r in execs.values()):
            _set_run_awaiting_human(session, run_id)
            return

        # Guard 3: next runnable node in topo order.
        nxt = None
        for key in order:
            r = execs[key]
            if r.status == "pending" and all(
                execs[p].status == "completed" for p in parents[key]
            ):
                nxt = r
                break
        if nxt is None:
            finalize_run(session, run_id, node_keys)
            return

        node = nodes_by_key[nxt.node_key]
        res = await run_node(
            session, run, nxt, node, parents[nxt.node_key], execs, executor=executor
        )
        if res is None:  # failed or lost race -> re-loop (guard 3 will finalize)
            continue

        _reassert_rls(session)
        if nxt.approver_user_ids:  # human-gated -> pause for review
            transition_node_status(
                session,
                nxt.id,
                from_status="running",
                to_status="awaiting_approval",
                extra_cols={"output": json.dumps(res.output)},
            )
            _set_run_awaiting_human(session, run_id)
            return
        transition_node_status(
            session,
            nxt.id,
            from_status="running",
            to_status="completed",
            extra_cols={"output": json.dumps(res.output)},
        )
        # continue loop
