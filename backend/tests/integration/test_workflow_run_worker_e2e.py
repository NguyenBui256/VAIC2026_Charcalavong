"""End-to-end — real arq Worker, real Redis, real Postgres. Story 3.2.

Proves the FULL skeleton described in Dev Notes: `POST /workflows/{id}/runs`
enqueues `run_workflow` with materialized tenant_id (AD-10); a real arq
Worker picks it up, bootstraps tenant context, CAS `pending -> running`,
then hands off to `orchestrate_run` (Story 3.3/3.4). Both tests here
monkeypatch `orchestrate_run` to a lightweight stub that just performs the
old T5.5 `running -> completed` transition -- these tests only prove the
CAS/tenant-plumbing skeleton (AC4/AC5/AC8/AC9); real decomposition/dispatch
behavior is covered by `test_orchestrator_execution.py`. Requires real
Redis (`VAIC_REDIS_URL`, see `.env`) and Postgres.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from arq import Worker, create_pool
from arq import func as arq_func
from arq.connections import RedisSettings
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import AdminSessionLocal
from app.core.jobs import TENANT_ID_KWARG
from app.core.settings import get_settings
from app.modules.orchestrator.models import Workflow, WorkflowRun
from app.modules.orchestrator.state import transition_and_audit
from app.workers import orchestrator_worker
from app.workers.orchestrator_worker import run_workflow
from tests.integration.conftest import login_token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _stub_orchestrate(session: Any, run_id: str, **_kwargs: Any) -> None:
    """Old T5.5 no-op behavior — CAS `running -> completed` only."""
    transition_and_audit(
        session, kind="run", entity_id=run_id, run_id=run_id,
        from_status="running", to_status="completed",
    )


async def test_e2e_run_workflow_transitions_pending_to_completed(
    agent_client: TestClient,
    agent_seed_data: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import redis.asyncio as aioredis
    from arq.connections import RedisSettings

    monkeypatch.setattr(orchestrator_worker, "orchestrate_run", _stub_orchestrate)
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    r = aioredis.from_url(get_settings().redis_url)
    await r.flushdb()
    await r.aclose()

    token = login_token(agent_client, "builder@tenantc.example")
    wf = agent_client.post(
        "/workflows",
        json={"name": "E2E WF", "description": "Prove the skeleton."},
        headers=_auth_headers(token),
    )
    assert wf.status_code == 201, wf.text
    workflow_id = wf.json()["data"]["id"]

    run_resp = agent_client.post(
        f"/workflows/{workflow_id}/runs",
        json={},
        headers=_auth_headers(token),
    )
    assert run_resp.status_code == 201, run_resp.text
    run_id = run_resp.json()["data"]["id"]
    assert run_resp.json()["data"]["status"] == "pending"

    worker = Worker(
        functions=[arq_func(run_workflow, name="run_workflow")],
        redis_settings=redis_settings,
        burst=True,
        max_jobs=2,
        job_timeout=30,
        max_tries=1,
    )
    await worker.run_check()

    with AdminSessionLocal() as s:
        row = s.execute(
            text("SELECT status FROM workflow_runs WHERE id=:id"),
            {"id": run_id},
        ).fetchone()
        audit_rows = s.execute(
            text(
                "SELECT type, input FROM audit_trail WHERE run_id=:rid ORDER BY ts"
            ),
            {"rid": run_id},
        ).fetchall()

    assert row[0] == "completed"
    assert len(audit_rows) == 2
    assert audit_rows[0][0] == "workflow_run.transition"
    assert audit_rows[0][1] == {"from": "pending", "to": "running"}
    assert audit_rows[1][1] == {"from": "running", "to": "completed"}

    # Cleanup
    with AdminSessionLocal() as s:
        s.execute(text("DELETE FROM audit_trail WHERE run_id=:id"), {"id": run_id})
        s.execute(text("DELETE FROM workflow_runs WHERE id=:id"), {"id": run_id})
        s.execute(text("DELETE FROM workflows WHERE id=:id"), {"id": workflow_id})
        s.commit()


async def test_e2e_resumed_run_workflow_reaches_completed(
    agent_seed_data: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression — resume=True path (AC8 crash recovery) must not be a no-op.

    Seeds a Run directly at `status='running'` (simulating a crash mid-flight
    — no CAS from `pending` ever happens for a resumed Run, mirroring what
    `resume_orphaned_runs` finds). Enqueues `run_workflow` the same way the
    poller does: `resume=True` + materialized `_tenant_id`, bypassing the
    `pending -> running` CAS entirely. Runs a REAL arq Worker (no mocking of
    the worker body) and asserts the Run actually reaches `completed`.

    Before the fix, `run_workflow` always CAS'd `pending -> running`
    regardless of `resume`; since the Run was already `running`, that CAS
    always lost the race and the function returned early — the Run stayed
    stuck at `running` forever. This test fails on the pre-fix code.
    """
    import redis.asyncio as aioredis

    monkeypatch.setattr(orchestrator_worker, "orchestrate_run", _stub_orchestrate)
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    r = aioredis.from_url(get_settings().redis_url)
    await r.flushdb()
    await r.aclose()

    workflow_id = uuid.uuid4()
    run_id = uuid.uuid4()
    tenant_id = agent_seed_data["tenant_agents_id"]
    with AdminSessionLocal() as s:
        s.add(
            Workflow(
                id=workflow_id,
                tenant_id=tenant_id,
                owner_id=agent_seed_data["builder_user_id"],
                name="Resume E2E WF",
                description="Simulates a crashed, orphaned Run.",
            )
        )
        s.flush()
        s.add(
            WorkflowRun(
                id=run_id,
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                status="running",
            )
        )
        s.commit()

    try:
        # Enqueue exactly as `resume_orphaned_runs` does: resume=True +
        # materialized _tenant_id (no caller contextvar in that sweep).
        pool = await create_pool(redis_settings)
        try:
            await pool.enqueue_job(
                "run_workflow",
                run_id=str(run_id),
                resume=True,
                **{TENANT_ID_KWARG: str(tenant_id)},
            )
        finally:
            await pool.aclose()

        worker = Worker(
            functions=[arq_func(run_workflow, name="run_workflow")],
            redis_settings=redis_settings,
            burst=True,
            max_jobs=2,
            job_timeout=30,
            max_tries=1,
        )
        await worker.run_check()

        with AdminSessionLocal() as s:
            row = s.execute(
                text("SELECT status FROM workflow_runs WHERE id=:id"),
                {"id": run_id},
            ).fetchone()
            audit_rows = s.execute(
                text(
                    "SELECT type, input FROM audit_trail WHERE run_id=:rid ORDER BY ts"
                ),
                {"rid": run_id},
            ).fetchall()

        assert row[0] == "completed"
        # Only the `running -> completed` transition is audited on the
        # resume path — the `pending -> running` CAS never ran.
        assert len(audit_rows) == 1
        assert audit_rows[0][0] == "workflow_run.transition"
        assert audit_rows[0][1] == {"from": "running", "to": "completed"}
    finally:
        with AdminSessionLocal() as s:
            s.execute(text("DELETE FROM audit_trail WHERE run_id=:id"), {"id": run_id})
            s.execute(text("DELETE FROM workflow_runs WHERE id=:id"), {"id": run_id})
            s.execute(text("DELETE FROM workflows WHERE id=:id"), {"id": workflow_id})
            s.commit()
