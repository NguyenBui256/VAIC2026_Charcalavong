"""Compare-and-set state machine for `workflow_runs` / `tasks` (AD-6).

Every status transition through this module uses the single
`UPDATE ... WHERE id=? AND status=?` pattern (Divergence 4/8) — never
SELECT-then-UPDATE. Callers MUST check the returned bool and abandon
cleanly on `False` (AC5/AC10) — never assume success.

`transition_run_status`/`transition_task_status` are the raw CAS
primitives — no audit side-effect. These are what the concurrency test
(T7.3) calls directly, so a race between two callers is observable purely
as `True`/`False` without an audit write muddying the assertion.

`transition_and_audit` wraps either primitive with the AC9 audit emission
(`workflow_run.transition`, real `run_id`/fresh `step_id` per AD-4) and is
what production call sites (routes, worker) must use — never call the raw
primitives directly outside a test.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.ids import utcnow_iso_ms, uuid7
from app.core.ports.audit import AuditEntry, AuditPort

__all__ = [
    "transition_run_status",
    "transition_task_status",
    "transition_and_audit",
]

_RUN_CAS_SET_CLAUSES = [
    "status=CAST(:to AS varchar)",
    "started_at = CASE WHEN CAST(:to AS varchar)='running' "
    "THEN now() ELSE started_at END",
    "ended_at = CASE WHEN CAST(:to AS varchar) IN ('completed','failed','timed_out') "
    "THEN now() ELSE ended_at END",
]


def transition_run_status(
    session: Session,
    run_id: uuid.UUID | str,
    *,
    from_status: str,
    to_status: str,
    extra_cols: dict[str, Any] | None = None,
) -> bool:
    """CAS `workflow_runs.status`. Returns True iff exactly one row updated.

    Commits immediately (the CAS `UPDATE`'s own row lock, under Postgres
    READ COMMITTED, is what serializes concurrent callers — Divergence 8;
    no `SELECT ... FOR UPDATE` needed).

    `extra_cols` mirrors `transition_task_status` — lets a caller (e.g.
    `orchestrate_run`) write `result` atomically with the `running ->
    completed` CAS instead of a separate post-commit UPDATE (AD-6: no
    window where the Run is `completed` with `result=NULL`).
    """
    set_clauses = list(_RUN_CAS_SET_CLAUSES)
    params: dict[str, Any] = {"to": to_status, "from": from_status, "id": str(run_id)}
    if extra_cols:
        set_clauses.extend(f"{key}=:{key}" for key in extra_cols)
        params.update(extra_cols)

    sql = text(
        f"UPDATE workflow_runs SET {', '.join(set_clauses)} "
        "WHERE id=:id AND status=CAST(:from AS varchar)"
    )
    result = session.execute(sql, params)
    session.commit()
    return result.rowcount == 1


def transition_task_status(
    session: Session,
    task_id: uuid.UUID | str,
    *,
    from_status: str,
    to_status: str,
    extra_cols: dict[str, Any] | None = None,
) -> bool:
    """CAS `tasks.status`. Mirrors `transition_run_status` for the Task table.

    `claimed_at`/`completed_at` are stamped via the same CASE pattern as
    the Run helper. Story 3.4's claim/complete calls build on this without
    re-deriving the CAS SQL string (single source of truth, per T3.2).
    """
    set_clauses = [
        "status=CAST(:to AS varchar)",
        "claimed_at = CASE WHEN CAST(:to AS varchar)='claimed' "
        "THEN now() ELSE claimed_at END",
        "completed_at = CASE WHEN CAST(:to AS varchar) IN ('completed','failed') "
        "THEN now() ELSE completed_at END",
    ]
    params: dict[str, Any] = {"to": to_status, "from": from_status, "id": str(task_id)}
    if extra_cols:
        set_clauses.extend(f"{key}=:{key}" for key in extra_cols)
        params.update(extra_cols)

    sql = text(
        f"UPDATE tasks SET {', '.join(set_clauses)} "
        "WHERE id=:id AND status=CAST(:from AS varchar)"
    )
    result = session.execute(sql, params)
    session.commit()
    return result.rowcount == 1


def transition_and_audit(
    session: Session,
    *,
    kind: Literal["run", "task"],
    entity_id: uuid.UUID | str,
    run_id: uuid.UUID | str,
    from_status: str,
    to_status: str,
    extra_cols: dict[str, Any] | None = None,
    audit: AuditPort | None = None,
) -> bool:
    """CAS transition + AC9 audit emission (Rule of Three: create/running,
    running/completed, running/failed already call this at T3.3 time).

    `run_id` is always the owning Workflow Run's id (`== entity_id` when
    `kind == "run"`) — `audit_trail` rows are always scoped to a Run, even
    when the entity being transitioned is a Task (Story 3.4).

    Audits EVERY attempt, including lost races (`rowcount=0`) — AC9's
    `output={rowcount}` shape is only meaningful if 0 is captured too.
    This is not a "side effect" in the AC5 sense (no further Run logic
    proceeds on a lost race); it is a diagnostic record of the attempt.
    """
    if kind == "run":
        ok = transition_run_status(
            session,
            entity_id,
            from_status=from_status,
            to_status=to_status,
            extra_cols=extra_cols,
        )
    else:
        ok = transition_task_status(
            session,
            entity_id,
            from_status=from_status,
            to_status=to_status,
            extra_cols=extra_cols,
        )

    (audit or PostgresAuditSink()).log(
        AuditEntry(
            run_id=str(run_id),
            step_id=str(uuid7()),
            # No Agent is involved in a bare transition (Dev Notes AD-4) —
            # empty string round-trips to NULL in PostgresAuditSink (the
            # `agent_id` column is nullable), unlike a non-UUID sentinel
            # string which would raise in `uuid.UUID(entry.agent_id)`.
            agent_id="",
            ts=utcnow_iso_ms(),
            type="workflow_run.transition",
            input={"from": from_status, "to": to_status},
            output={"rowcount": 1 if ok else 0},
            latency_ms=0,
            model="",
        )
    )
    return ok
