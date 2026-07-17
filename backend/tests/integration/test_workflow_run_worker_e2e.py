"""End-to-end — real arq Worker, real Redis, real Postgres. Story 3.2.

Proves the FULL skeleton described in Dev Notes: `POST /workflows/{id}/runs`
enqueues `run_workflow` with materialized tenant_id (AD-10); a real arq
Worker picks it up, bootstraps tenant context, CAS `pending -> running`,
then (T5.5 stub) CAS `running -> completed`; both transitions are audited
(AC9). Requires real Redis (`VAIC_REDIS_URL`, see `.env`) and Postgres.
"""

from __future__ import annotations

from typing import Any

from arq import Worker
from arq import func as arq_func
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import AdminSessionLocal
from app.core.settings import get_settings
from app.workers.orchestrator_worker import run_workflow
from tests.integration.conftest import login_token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_e2e_run_workflow_transitions_pending_to_completed(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    import redis.asyncio as aioredis
    from arq.connections import RedisSettings

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
