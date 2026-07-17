"""AC4, AC5, AC6, AC10 — CAS state machine (`transition_run_status` /
`transition_task_status`) tests. Story 3.2.

AC10's concurrency test is LOAD-BEARING (Divergence 4/8): two threads race
the SAME `pending -> running` transition on the same Run; exactly one must
observe `rowcount==1` (`True`), the other `rowcount==0` (`False`). Postgres
READ COMMITTED's row lock on the CAS `UPDATE` itself provides the
serialization (Dev Notes "Isolation-Level Note") — no `SELECT ... FOR
UPDATE` needed.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import AdminSessionLocal, SessionLocal
from app.modules.orchestrator.models import Task, Workflow, WorkflowRun
from app.modules.orchestrator.state import transition_run_status, transition_task_status


def _as_app(session: Session, tenant_id: uuid.UUID) -> None:
    session.execute(text("SET LOCAL ROLE vaic_app"))
    session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


@pytest.fixture()
def seeded_run(agent_seed_data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    workflow_id = uuid.uuid4()
    run_id = uuid.uuid4()
    with AdminSessionLocal() as s:
        s.add(
            Workflow(
                id=workflow_id,
                tenant_id=agent_seed_data["tenant_agents_id"],
                owner_id=agent_seed_data["builder_user_id"],
                name="State Machine WF",
                description="Prove the CAS skeleton.",
            )
        )
        s.flush()
        s.add(
            WorkflowRun(
                id=run_id,
                tenant_id=agent_seed_data["tenant_agents_id"],
                workflow_id=workflow_id,
                status="pending",
            )
        )
        s.commit()
    try:
        yield {**agent_seed_data, "workflow_id": workflow_id, "run_id": run_id}
    finally:
        with AdminSessionLocal() as s:
            s.execute(text("DELETE FROM workflow_runs WHERE id=:id"), {"id": str(run_id)})
            s.execute(text("DELETE FROM workflows WHERE id=:id"), {"id": str(workflow_id)})
            s.commit()


@pytest.fixture()
def seeded_task(seeded_agent: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Depends on `seeded_agent` (conftest) for a valid `target_agent_id` FK."""
    workflow_id = uuid.uuid4()
    run_id = uuid.uuid4()
    task_id = uuid.uuid4()
    with AdminSessionLocal() as s:
        s.add(
            Workflow(
                id=workflow_id,
                tenant_id=seeded_agent["tenant_agents_id"],
                owner_id=seeded_agent["builder_user_id"],
                name="Task CAS WF",
                description="Prove the Task CAS skeleton.",
            )
        )
        s.flush()
        s.add(
            WorkflowRun(
                id=run_id,
                tenant_id=seeded_agent["tenant_agents_id"],
                workflow_id=workflow_id,
                status="running",
            )
        )
        s.flush()
        s.add(
            Task(
                id=task_id,
                tenant_id=seeded_agent["tenant_agents_id"],
                run_id=run_id,
                target_agent_id=seeded_agent["agent_a_id"],
                status="pending",
                schema_payload={"task": "verify credit score"},
            )
        )
        s.commit()
    try:
        yield {**seeded_agent, "workflow_id": workflow_id, "run_id": run_id, "task_id": task_id}
    finally:
        with AdminSessionLocal() as s:
            s.execute(text("DELETE FROM tasks WHERE id=:id"), {"id": str(task_id)})
            s.execute(text("DELETE FROM workflow_runs WHERE id=:id"), {"id": str(run_id)})
            s.execute(text("DELETE FROM workflows WHERE id=:id"), {"id": str(workflow_id)})
            s.commit()


# ---------------------------------------------------------------------------
# AC4 — CAS pending -> running success
# ---------------------------------------------------------------------------


def test_transition_run_status_pending_to_running_succeeds(
    seeded_run: dict[str, Any],
) -> None:
    with SessionLocal() as s:
        _as_app(s, seeded_run["tenant_agents_id"])
        ok = transition_run_status(
            s, seeded_run["run_id"], from_status="pending", to_status="running"
        )
    assert ok is True

    with AdminSessionLocal() as s:
        row = s.execute(
            text("SELECT status, started_at FROM workflow_runs WHERE id=:id"),
            {"id": str(seeded_run["run_id"])},
        ).fetchone()
    assert row[0] == "running"
    assert row[1] is not None


def test_transition_run_status_wrong_from_status_returns_false(
    seeded_run: dict[str, Any],
) -> None:
    """AC5/AC6 — CAS guard rejects a transition whose current status doesn't match."""
    with SessionLocal() as s:
        _as_app(s, seeded_run["tenant_agents_id"])
        ok = transition_run_status(
            s, seeded_run["run_id"], from_status="running", to_status="completed"
        )
    assert ok is False

    with AdminSessionLocal() as s:
        row = s.execute(
            text("SELECT status FROM workflow_runs WHERE id=:id"),
            {"id": str(seeded_run["run_id"])},
        ).fetchone()
    # Untouched — still 'pending'.
    assert row[0] == "pending"


def test_transition_run_status_terminal_sets_ended_at(
    seeded_run: dict[str, Any],
) -> None:
    with SessionLocal() as s:
        _as_app(s, seeded_run["tenant_agents_id"])
        transition_run_status(
            s, seeded_run["run_id"], from_status="pending", to_status="running"
        )
        ok = transition_run_status(
            s, seeded_run["run_id"], from_status="running", to_status="completed"
        )
    assert ok is True

    with AdminSessionLocal() as s:
        row = s.execute(
            text("SELECT status, ended_at FROM workflow_runs WHERE id=:id"),
            {"id": str(seeded_run["run_id"])},
        ).fetchone()
    assert row[0] == "completed"
    assert row[1] is not None


# ---------------------------------------------------------------------------
# AC10 — LOAD-BEARING concurrency test (Divergence 4/8)
# ---------------------------------------------------------------------------


def test_concurrent_pending_to_running_exactly_one_wins(
    seeded_run: dict[str, Any],
) -> None:
    """Two threads/sessions race the SAME transition; exactly one succeeds."""
    results: list[bool] = []
    results_lock = threading.Lock()

    def _attempt() -> None:
        with SessionLocal() as s:
            _as_app(s, seeded_run["tenant_agents_id"])
            ok = transition_run_status(
                s, seeded_run["run_id"], from_status="pending", to_status="running"
            )
        with results_lock:
            results.append(ok)

    t1 = threading.Thread(target=_attempt)
    t2 = threading.Thread(target=_attempt)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert sorted(results) == [False, True], f"expected exactly one winner, got {results}"

    with AdminSessionLocal() as s:
        row = s.execute(
            text("SELECT status FROM workflow_runs WHERE id=:id"),
            {"id": str(seeded_run["run_id"])},
        ).fetchone()
    assert row[0] == "running"


# ---------------------------------------------------------------------------
# T3.2 — Task CAS mirrors the Run helper
# ---------------------------------------------------------------------------


def test_transition_task_status_pending_to_claimed_succeeds(
    seeded_task: dict[str, Any],
) -> None:
    with SessionLocal() as s:
        _as_app(s, seeded_task["tenant_agents_id"])
        ok = transition_task_status(
            s, seeded_task["task_id"], from_status="pending", to_status="claimed"
        )
    assert ok is True

    with AdminSessionLocal() as s:
        row = s.execute(
            text("SELECT status, claimed_at FROM tasks WHERE id=:id"),
            {"id": str(seeded_task["task_id"])},
        ).fetchone()
    assert row[0] == "claimed"
    assert row[1] is not None


def test_transition_task_status_wrong_from_status_returns_false(
    seeded_task: dict[str, Any],
) -> None:
    with SessionLocal() as s:
        _as_app(s, seeded_task["tenant_agents_id"])
        ok = transition_task_status(
            s, seeded_task["task_id"], from_status="claimed", to_status="completed"
        )
    assert ok is False
