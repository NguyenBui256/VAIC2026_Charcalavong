"""AC1, AC3, AC4, AC10 — /workflows CRUD API tests (Story 3.1).

Test plan (AC # → test name):
- AC1  POST /workflows creates a scoped Workflow (201)
       -> test_post_workflows_creates_scoped_workflow_201
- AC3  GET /workflows is tenant-scoped
       -> test_list_workflows_is_tenant_scoped
       -> test_list_workflows_search_and_owner_filter
- AC4  Cross-tenant GET returns 404, not 403
       -> test_cross_tenant_get_returns_404_not_403
- AC10 builder role required to create/mutate; read/list open to any user
       -> test_post_workflows_non_builder_returns_403
       -> test_patch_non_builder_returns_403
       -> test_get_and_list_allowed_for_non_builder

Reuses `agent_client`/`agent_seed_data` fixtures from conftest.py — those
already provide a builder + operator user in a dedicated tenant plus a
cross-tenant user (bob), which is all Workflow CRUD needs (no department
scope on Workflows).
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

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
            "constraints": ["must check credit score"],
        },
        headers=_auth_headers(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]


# ---------------------------------------------------------------------------
# AC1 — POST /workflows creates a scoped Workflow (201)
# ---------------------------------------------------------------------------

def test_post_workflows_creates_scoped_workflow_201(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    data = _create_workflow(agent_client, token)
    assert data["tenant_id"] == str(agent_seed_data["tenant_agents_id"])
    assert data["owner_id"] == str(agent_seed_data["builder_user_id"])
    assert data["version"] == 1
    assert data["constraints"] == ["must check credit score"]
    assert data["confidence_threshold"] == 0.7
    assert data["escalation_timeout_seconds"] == 300
    assert "created_at" in data
    import uuid as _uuid

    parsed = _uuid.UUID(data["id"])
    assert parsed.version == 7


def test_post_workflows_non_builder_returns_403(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "operator@tenantc.example")
    r = agent_client.post(
        "/workflows",
        json={"name": "Nope", "description": "x"},
        headers=_auth_headers(token),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# GET /workflows/{id} round-trip + AC4 cross-tenant 404
# ---------------------------------------------------------------------------

def test_get_workflow_returns_same_record(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    created = _create_workflow(agent_client, token)
    r = agent_client.get(f"/workflows/{created['id']}", headers=_auth_headers(token))
    assert r.status_code == 200
    assert r.json()["data"] == created


def test_cross_tenant_get_returns_404_not_403(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    builder_token = login_token(agent_client, "builder@tenantc.example")
    created = _create_workflow(agent_client, builder_token)
    bob_token = login_token(agent_client, "bob@tenantb.example")
    r = agent_client.get(f"/workflows/{created['id']}", headers=_auth_headers(bob_token))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


# ---------------------------------------------------------------------------
# AC3 — List is tenant-scoped, search + owner filter
# ---------------------------------------------------------------------------

def test_list_workflows_is_tenant_scoped(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    builder_token = login_token(agent_client, "builder@tenantc.example")
    _create_workflow(agent_client, builder_token, name="TenantC-only Workflow")

    r = agent_client.get("/workflows", headers=_auth_headers(builder_token))
    assert r.status_code == 200
    names = {w["name"] for w in r.json()["data"]}
    assert "TenantC-only Workflow" in names

    bob_token = login_token(agent_client, "bob@tenantb.example")
    r2 = agent_client.get("/workflows", headers=_auth_headers(bob_token))
    assert r2.status_code == 200
    names_b = {w["name"] for w in r2.json()["data"]}
    assert "TenantC-only Workflow" not in names_b


def test_list_workflows_search_and_owner_filter(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    builder_token = login_token(agent_client, "builder@tenantc.example")
    created = _create_workflow(agent_client, builder_token, name="Searchable Loan Flow")
    _create_workflow(agent_client, builder_token, name="Other Flow")

    r = agent_client.get(
        "/workflows",
        params={"search": "Searchable"},
        headers=_auth_headers(builder_token),
    )
    assert r.status_code == 200
    names = {w["name"] for w in r.json()["data"]}
    assert "Searchable Loan Flow" in names
    assert "Other Flow" not in names

    r2 = agent_client.get(
        "/workflows",
        params={"owner_id": created["owner_id"]},
        headers=_auth_headers(builder_token),
    )
    assert r2.status_code == 200
    names2 = {w["name"] for w in r2.json()["data"]}
    assert "Searchable Loan Flow" in names2
    assert "Other Flow" in names2


# ---------------------------------------------------------------------------
# AC10 — read/list allowed for non-builder; PATCH requires builder
# ---------------------------------------------------------------------------

def test_get_and_list_allowed_for_non_builder(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    builder_token = login_token(agent_client, "builder@tenantc.example")
    created = _create_workflow(agent_client, builder_token)

    operator_token = login_token(agent_client, "operator@tenantc.example")
    r = agent_client.get(
        f"/workflows/{created['id']}", headers=_auth_headers(operator_token)
    )
    assert r.status_code == 200

    r_list = agent_client.get("/workflows", headers=_auth_headers(operator_token))
    assert r_list.status_code == 200


def test_patch_non_builder_returns_403(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    builder_token = login_token(agent_client, "builder@tenantc.example")
    created = _create_workflow(agent_client, builder_token)

    operator_token = login_token(agent_client, "operator@tenantc.example")
    r = agent_client.patch(
        f"/workflows/{created['id']}",
        json={"name": "Hacked"},
        headers=_auth_headers(operator_token),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


def test_patch_builder_updates_and_bumps_version(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    builder_token = login_token(agent_client, "builder@tenantc.example")
    created = _create_workflow(agent_client, builder_token)

    # A DIFFERENT builder in the same tenant may edit too — Workflows have
    # no department scope (T3.5: any builder in the tenant may edit).
    builder2_token = login_token(agent_client, "builder2@tenantc.example")
    r = agent_client.patch(
        f"/workflows/{created['id']}",
        json={"name": "Renamed Flow", "confidence_threshold": 0.9},
        headers=_auth_headers(builder2_token),
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["name"] == "Renamed Flow"
    assert data["confidence_threshold"] == 0.9
    assert data["version"] == 2
