"""AC8 — startup resume poller (`resume_orphaned_runs`). Story 3.2 T7.4.

Seeds a `status='running'` Run (simulating a crash mid-flight — no worker
process is alive to CAS it further), invokes the poller function directly
with a fake arq pool stashed on `ctx["arq_redis"]`, and asserts it
re-enqueues `run_workflow` with the Run's own materialized `tenant_id`.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import text

from app.core.db import AdminSessionLocal
from app.modules.orchestrator.models import Workflow, WorkflowRun
from app.workers.orchestrator_worker import resume_orphaned_runs


class _FakeArqPool:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, dict[str, Any]]] = []

    async def enqueue_job(self, job_name: str, **kwargs: Any) -> SimpleNamespace:
        self.enqueued.append((job_name, kwargs))
        return SimpleNamespace(job_id="fake-job-id")


@pytest.fixture()
def orphaned_run(agent_seed_data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    workflow_id = uuid.uuid4()
    run_id = uuid.uuid4()
    with AdminSessionLocal() as s:
        s.add(
            Workflow(
                id=workflow_id,
                tenant_id=agent_seed_data["tenant_agents_id"],
                owner_id=agent_seed_data["builder_user_id"],
                name="Resume WF",
                description="Simulates a crashed Run.",
            )
        )
        s.flush()
        s.add(
            WorkflowRun(
                id=run_id,
                tenant_id=agent_seed_data["tenant_agents_id"],
                workflow_id=workflow_id,
                status="running",
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


async def test_resume_orphaned_runs_reenqueues_running_run(
    orphaned_run: dict[str, Any],
) -> None:
    pool = _FakeArqPool()
    ctx: dict[str, Any] = {"arq_redis": pool}

    await resume_orphaned_runs(ctx)

    matches = [
        kwargs
        for name, kwargs in pool.enqueued
        if name == "run_workflow" and kwargs.get("run_id") == str(orphaned_run["run_id"])
    ]
    assert len(matches) == 1
    # Materialized tenant_id, sourced from the Run row's OWN tenant_id — not
    # any caller contextvar (this sweep runs under BYPASSRLS, AD-10).
    assert matches[0]["_tenant_id"] == str(orphaned_run["tenant_agents_id"])
    # `enqueued_jobs` is stashed on ctx for caller/test inspection.
    assert len(ctx["enqueued_jobs"]) == 1


async def test_resume_orphaned_runs_ignores_non_running_runs(
    orphaned_run: dict[str, Any],
) -> None:
    """A `pending`/`completed` Run is not picked up by the resume sweep."""
    with AdminSessionLocal() as s:
        s.execute(
            text("UPDATE workflow_runs SET status='completed' WHERE id=:id"),
            {"id": str(orphaned_run["run_id"])},
        )
        s.commit()

    pool = _FakeArqPool()
    await resume_orphaned_runs({"arq_redis": pool})

    matches = [
        kwargs
        for name, kwargs in pool.enqueued
        if kwargs.get("run_id") == str(orphaned_run["run_id"])
    ]
    assert matches == []


async def test_resume_orphaned_runs_requires_pool_in_ctx() -> None:
    with pytest.raises(RuntimeError, match="arq_redis"):
        await resume_orphaned_runs({})
