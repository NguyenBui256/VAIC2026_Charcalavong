"""AC2, AC3 — `POST /workflows/{id}/runs` API tests (Story 3.2).

Test plan (AC # -> test name):
- AC2  POST /workflows/{id}/runs creates a pending Run (201)
       -> test_post_runs_creates_pending_run_201
- AC3  arq job enqueued with materialized tenant_id
       -> test_post_runs_enqueues_run_workflow_with_tenant_id
- Cross-tenant / missing workflow_id -> 404 (RLS-backed, mirrors Workflow GET)
       -> test_post_runs_unknown_workflow_returns_404

Overrides the `get_arq_pool` FastAPI dependency with an in-memory fake so
this test never needs a real Redis connection — only the CAS/worker tests
(Story 3.2 T7.3/T7.4) and the AD-10 arq boundary tests need real Redis.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.arq_pool import get_arq_pool
from app.main import app as fastapi_app
from tests.integration.conftest import login_token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_workflow(
    client: TestClient, token: str, *, name: str = "Loan Intake"
) -> dict[str, Any]:
    r = client.post(
        "/workflows",
        json={
            "name": name,
            "description": "Handle inbound loan requests end to end.",
        },
        headers=_auth_headers(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]


class _FakeArqPool:
    """In-memory stand-in for `ArqRedis` — records `enqueue_job` calls."""

    def __init__(self) -> None:
        self.enqueued: list[tuple[str, dict[str, Any]]] = []

    async def enqueue_job(
        self, job_name: str, *, _job_id: str | None = None, **kwargs: Any
    ) -> SimpleNamespace:
        self.enqueued.append((job_name, kwargs))
        return SimpleNamespace(job_id="fake-job-id")


@pytest.fixture()
def fake_arq_pool() -> Iterator[_FakeArqPool]:
    pool = _FakeArqPool()
    fastapi_app.dependency_overrides[get_arq_pool] = lambda: pool
    try:
        yield pool
    finally:
        fastapi_app.dependency_overrides.pop(get_arq_pool, None)


# ---------------------------------------------------------------------------
# AC2 — POST /workflows/{id}/runs creates a pending Run (201)
# ---------------------------------------------------------------------------


def test_post_runs_creates_pending_run_201(
    agent_client: TestClient,
    agent_seed_data: dict[str, Any],
    fake_arq_pool: _FakeArqPool,
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    workflow = _create_workflow(agent_client, token)

    r = agent_client.post(
        f"/workflows/{workflow['id']}/runs",
        json={"input": {"applicant": "Jane Doe"}},
        headers=_auth_headers(token),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]

    assert data["status"] == "pending"
    assert data["workflow_id"] == workflow["id"]
    assert data["tenant_id"] == workflow["tenant_id"]
    assert data["input"] == {"applicant": "Jane Doe"}
    assert data["result"] is None
    assert data["started_at"] is None
    assert data["ended_at"] is None
    assert "created_at" in data
    assert uuid.UUID(data["id"]).version == 7


def test_post_runs_defaults_input_to_empty_dict(
    agent_client: TestClient,
    agent_seed_data: dict[str, Any],
    fake_arq_pool: _FakeArqPool,
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    workflow = _create_workflow(agent_client, token, name="No Input Flow")

    r = agent_client.post(
        f"/workflows/{workflow['id']}/runs",
        json={},
        headers=_auth_headers(token),
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["input"] == {}


# ---------------------------------------------------------------------------
# AC3 — arq job enqueued with materialized tenant_id
# ---------------------------------------------------------------------------


def test_post_runs_enqueues_run_workflow_with_tenant_id(
    agent_client: TestClient,
    agent_seed_data: dict[str, Any],
    fake_arq_pool: _FakeArqPool,
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    workflow = _create_workflow(agent_client, token, name="Enqueue Check Flow")

    r = agent_client.post(
        f"/workflows/{workflow['id']}/runs",
        json={},
        headers=_auth_headers(token),
    )
    assert r.status_code == 201, r.text
    run_id = r.json()["data"]["id"]

    assert len(fake_arq_pool.enqueued) == 1
    job_name, kwargs = fake_arq_pool.enqueued[0]
    assert job_name == "run_workflow"
    assert kwargs["run_id"] == run_id
    # `_tenant_id` is `enqueue_job_with_context`'s materialized kwarg (AD-10).
    assert kwargs["_tenant_id"] == workflow["tenant_id"]


# ---------------------------------------------------------------------------
# Cross-tenant / missing workflow_id -> 404 (RLS-backed via `get_workflow`)
# ---------------------------------------------------------------------------


def test_post_runs_unknown_workflow_returns_404(
    agent_client: TestClient,
    agent_seed_data: dict[str, Any],
    fake_arq_pool: _FakeArqPool,
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    r = agent_client.post(
        f"/workflows/{uuid.uuid4()}/runs",
        json={},
        headers=_auth_headers(token),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
    assert fake_arq_pool.enqueued == []
