"""Integration tests for Task dispatch + aggregation + worker wiring
(Story 3.3/3.4, Tasks 5-7).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import AdminSessionLocal
from app.core.ports.agent_provider import TaskExecutionResult
from app.modules.orchestrator.models import Task, WorkflowRun
from tests.integration.test_orchestrator_decomposition import (
    FakeLlm,
    _as_app,
    seeded_run_with_two_agents,  # noqa: F401 -- reused fixture
)

_ = seeded_run_with_two_agents  # keep the import "used" for linters


class FakeExecutor:
    def __init__(self, res: TaskExecutionResult) -> None:
        self._res = res

    async def execute_task(self, agent_id, payload, *, tenant_id, department_id):
        return self._res


@pytest.fixture()
def seeded_pending_task(
    app_session: Session,
    seeded_run_with_two_agents: tuple[WorkflowRun, uuid.UUID, uuid.UUID],
) -> Iterator[Task]:
    """One `pending` Task targeting agent_a, in the seeded Run's tenant."""
    run, agent_a_id, _agent_b_id = seeded_run_with_two_agents
    task_id = uuid.uuid4()
    with AdminSessionLocal() as s:
        s.add(
            Task(
                id=task_id, tenant_id=run.tenant_id, run_id=run.id,
                target_agent_id=agent_a_id, status="pending",
                schema_payload={"task": {"summary": "screen"}, "input": {}, "criteria": {}},
            )
        )
        s.commit()
    task = app_session.get(Task, task_id)
    yield task


async def test_execute_task_row_completes(
    app_session: Session, seeded_pending_task: Task
) -> None:
    from app.modules.orchestrator.service import execute_task_row

    task = seeded_pending_task
    ex = FakeExecutor(TaskExecutionResult(output={"verdict": "pass"}, confidence=0.8))
    await execute_task_row(app_session, task, executor=ex)
    app_session.expire(task)
    assert task.status == "completed"
    assert task.result["output"]["verdict"] == "pass"


async def test_orchestrate_run_end_to_end(
    app_session: Session,
    seeded_run_with_two_agents: tuple[WorkflowRun, uuid.UUID, uuid.UUID],
) -> None:
    from app.modules.orchestrator.service import orchestrate_run

    run, a_id, b_id = seeded_run_with_two_agents
    payload = [
        {"task": {"summary": f"t{i}"}, "target_agent_id": str(aid), "input": {},
         "output": {}, "expected": [], "criteria": {}}
        for i, aid in enumerate([a_id, b_id])
    ]
    execu = FakeExecutor(TaskExecutionResult(output={"ok": True}, confidence=0.9))
    await orchestrate_run(app_session, run.id, llm=FakeLlm(payload), executor=execu)

    # `run` is a detached instance seeded via a separate AdminSessionLocal
    # (see `seeded_run_with_two_agents`), never loaded into `app_session` --
    # re-fetch fresh instead of `expire()`ing an instance not persistent
    # within this session.
    app_session.expire_all()
    updated = app_session.get(WorkflowRun, run.id)
    assert updated.status == "completed"
    assert len(updated.result["tasks"]) == 2
    assert all(t["result"]["output"]["ok"] is True for t in updated.result["tasks"])


async def test_orchestrate_run_fails_when_no_task_succeeds(
    app_session: Session,
    seeded_run_with_two_agents: tuple[WorkflowRun, uuid.UUID, uuid.UUID],
) -> None:
    """M-3: every Task ends `completed` with `result.success=False` (M-4 tool
    failure, not an infra error) -> the Run must end `failed`, not
    `completed` -- a Run with zero actually-successful Tasks is not a
    success."""
    from app.modules.orchestrator.service import orchestrate_run

    run, a_id, b_id = seeded_run_with_two_agents
    payload = [
        {"task": {"summary": f"t{i}"}, "target_agent_id": str(aid), "input": {},
         "output": {}, "expected": [], "criteria": {}}
        for i, aid in enumerate([a_id, b_id])
    ]
    execu = FakeExecutor(
        TaskExecutionResult(
            output={"ok": False}, confidence=0.9, success=False, error="tool failed"
        )
    )
    await orchestrate_run(app_session, run.id, llm=FakeLlm(payload), executor=execu)

    app_session.expire_all()
    updated = app_session.get(WorkflowRun, run.id)
    assert updated.status == "failed"
    assert len(updated.result["tasks"]) == 2


async def test_orchestrate_run_completes_when_at_least_one_task_succeeds(
    app_session: Session,
    seeded_run_with_two_agents: tuple[WorkflowRun, uuid.UUID, uuid.UUID],
) -> None:
    """M-3 counterpart: >=1 succeeding Task (of N) is still enough for the
    Run to end `completed` -- only an all-failed Run flips to `failed`."""
    from app.modules.orchestrator.service import orchestrate_run

    run, a_id, b_id = seeded_run_with_two_agents
    payload = [
        {"task": {"summary": f"t{i}"}, "target_agent_id": str(aid), "input": {},
         "output": {}, "expected": [], "criteria": {}}
        for i, aid in enumerate([a_id, b_id])
    ]

    class MixedExecutor:
        def __init__(self) -> None:
            self._calls = 0

        async def execute_task(self, agent_id, payload, *, tenant_id, department_id):
            self._calls += 1
            ok = self._calls == 1
            return TaskExecutionResult(
                output={"ok": ok}, confidence=0.9, success=ok, error="" if ok else "boom"
            )

    await orchestrate_run(app_session, run.id, llm=FakeLlm(payload), executor=MixedExecutor())

    app_session.expire_all()
    updated = app_session.get(WorkflowRun, run.id)
    assert updated.status == "completed"


async def test_run_workflow_calls_orchestrate(
    app_session: Session,
    seeded_run_with_two_agents: tuple[WorkflowRun, uuid.UUID, uuid.UUID],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker wiring — `run_workflow`'s post-CAS body must call `orchestrate_run`
    (adapted to the real `orchestrator_worker.py` structure -- no `jobs.py` /
    `_run_workflow_body` exists there; `orchestrate_run` is patched directly
    on the worker module).
    """
    from app.workers import orchestrator_worker as workermod

    run, _a_id, _b_id = seeded_run_with_two_agents
    # Reset the seeded Run to `pending` so the worker's CAS has something to win.
    _as_app(app_session, run.tenant_id)
    app_session.execute(
        text("UPDATE workflow_runs SET status='pending' WHERE id=:id"), {"id": str(run.id)}
    )
    app_session.commit()

    called: dict[str, Any] = {}

    async def spy(session, run_id, **kwargs):
        called["run_id"] = run_id

    monkeypatch.setattr(workermod, "orchestrate_run", spy)

    ctx: dict[str, Any] = {"session": app_session}
    await workermod.run_workflow.__wrapped__(ctx, run_id=str(run.id))

    assert called["run_id"] == str(run.id)
