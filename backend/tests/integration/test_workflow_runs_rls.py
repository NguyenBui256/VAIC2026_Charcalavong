"""AC1, AC7 — RLS applied to `workflow_runs` + `tasks`; raw SQL cross-tenant empty.

Mirrors `test_workflows_rls.py`'s pattern: `SET LOCAL ROLE vaic_app` to drop
superuser privileges, then verify tenant isolation via ORM and raw SQL.
Reuses `seeded_agent` (extends `agent_seed_data` with `agent_a_id`/
`agent_b_id`) so `tasks.target_agent_id` has a valid FK target per tenant.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.orchestrator.models import Task, Workflow, WorkflowRun


@pytest.fixture()
def seeded_run_and_task(seeded_agent: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Seed one Workflow + WorkflowRun + Task row per tenant (A + B)."""
    from app.core.db import AdminSessionLocal

    workflow_a_id = uuid.uuid4()
    workflow_b_id = uuid.uuid4()
    run_a_id = uuid.uuid4()
    run_b_id = uuid.uuid4()
    task_a_id = uuid.uuid4()
    task_b_id = uuid.uuid4()

    with AdminSessionLocal() as s:
        s.add(
            Workflow(
                id=workflow_a_id,
                tenant_id=seeded_agent["tenant_agents_id"],
                owner_id=seeded_agent["builder_user_id"],
                name="Workflow A",
                description="Handle loan requests.",
            )
        )
        s.add(
            Workflow(
                id=workflow_b_id,
                tenant_id=seeded_agent["tenant_b_id"],
                owner_id=seeded_agent["user_b_id"],
                name="Workflow B",
                description="Handle HR requests.",
            )
        )
        s.flush()
        s.add(
            WorkflowRun(
                id=run_a_id,
                tenant_id=seeded_agent["tenant_agents_id"],
                workflow_id=workflow_a_id,
                status="pending",
            )
        )
        s.add(
            WorkflowRun(
                id=run_b_id,
                tenant_id=seeded_agent["tenant_b_id"],
                workflow_id=workflow_b_id,
                status="pending",
            )
        )
        s.flush()
        s.add(
            Task(
                id=task_a_id,
                tenant_id=seeded_agent["tenant_agents_id"],
                run_id=run_a_id,
                target_agent_id=seeded_agent["agent_a_id"],
                status="pending",
                schema_payload={"task": "verify credit score"},
            )
        )
        s.add(
            Task(
                id=task_b_id,
                tenant_id=seeded_agent["tenant_b_id"],
                run_id=run_b_id,
                target_agent_id=seeded_agent["agent_b_id"],
                status="pending",
                schema_payload={"task": "verify HR record"},
            )
        )
        s.commit()
    try:
        yield {
            **seeded_agent,
            "workflow_a_id": workflow_a_id,
            "workflow_b_id": workflow_b_id,
            "run_a_id": run_a_id,
            "run_b_id": run_b_id,
            "task_a_id": task_a_id,
            "task_b_id": task_b_id,
        }
    finally:
        with AdminSessionLocal() as s:
            s.execute(
                text("DELETE FROM tasks WHERE id IN (:a, :b)"),
                {"a": str(task_a_id), "b": str(task_b_id)},
            )
            s.execute(
                text("DELETE FROM workflow_runs WHERE id IN (:a, :b)"),
                {"a": str(run_a_id), "b": str(run_b_id)},
            )
            s.execute(
                text("DELETE FROM workflows WHERE id IN (:a, :b)"),
                {"a": str(workflow_a_id), "b": str(workflow_b_id)},
            )
            s.commit()


def _as_app(session: Session, tenant_id: uuid.UUID) -> None:
    session.execute(text("SET LOCAL ROLE vaic_app"))
    session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"),
        {"tid": str(tenant_id)},
    )


# ---------------------------------------------------------------------------
# AC1/AC7 — RLS ENABLE + FORCE + policy on both new tables
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("table", ["workflow_runs", "tasks"])
def test_rls_enabled_and_forced(table: str, seeded_run_and_task: dict[str, Any]) -> None:
    from app.core.db import AdminSessionLocal

    with AdminSessionLocal() as s:
        row = s.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname = :t"
            ),
            {"t": table},
        ).fetchone()
    assert row is not None
    assert row[0] is True
    assert row[1] is True


@pytest.mark.parametrize("table", ["workflow_runs", "tasks"])
def test_rls_policy_uses_tenant_id(table: str, seeded_run_and_task: dict[str, Any]) -> None:
    from app.core.db import AdminSessionLocal

    with AdminSessionLocal() as s:
        policies = s.execute(
            text(
                "SELECT policyname, qual, with_check FROM pg_policies "
                "WHERE tablename = :t"
            ),
            {"t": table},
        ).fetchall()
    assert len(policies) >= 1
    for _name, qual, check in policies:
        assert "tenant_id" in str(qual).lower()
        assert "tenant_id" in str(check).lower()


# ---------------------------------------------------------------------------
# Tenant isolation — ORM + raw SQL
# ---------------------------------------------------------------------------


def test_tenant_a_sees_own_run_and_task_orm(
    app_session: Session, seeded_run_and_task: dict[str, Any]
) -> None:
    _as_app(app_session, seeded_run_and_task["tenant_agents_id"])
    runs = app_session.execute(select(WorkflowRun)).scalars().all()
    run_ids = {r.id for r in runs}
    assert seeded_run_and_task["run_a_id"] in run_ids
    assert seeded_run_and_task["run_b_id"] not in run_ids

    tasks = app_session.execute(select(Task)).scalars().all()
    task_ids = {t.id for t in tasks}
    assert seeded_run_and_task["task_a_id"] in task_ids
    assert seeded_run_and_task["task_b_id"] not in task_ids


def test_cross_tenant_orm_query_returns_empty(
    app_session: Session, seeded_run_and_task: dict[str, Any]
) -> None:
    _as_app(app_session, seeded_run_and_task["tenant_agents_id"])
    rows = (
        app_session.execute(
            select(WorkflowRun).where(
                WorkflowRun.id == seeded_run_and_task["run_b_id"]
            )
        )
        .scalars()
        .all()
    )
    assert rows == []


def test_cross_tenant_raw_sql_query_returns_empty(
    app_session: Session, seeded_run_and_task: dict[str, Any]
) -> None:
    _as_app(app_session, seeded_run_and_task["tenant_agents_id"])
    result = app_session.execute(
        text("SELECT status FROM workflow_runs WHERE id = :rid"),
        {"rid": str(seeded_run_and_task["run_b_id"])},
    ).fetchall()
    assert result == []

    result_task = app_session.execute(
        text("SELECT status FROM tasks WHERE id = :tid"),
        {"tid": str(seeded_run_and_task["task_b_id"])},
    ).fetchall()
    assert result_task == []
