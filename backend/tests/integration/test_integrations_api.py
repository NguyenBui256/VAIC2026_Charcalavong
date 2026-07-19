"""T9.2 — /agents/{id}/integrations API: CRUD, RLS, masked response, authz.

AC1  POST returns 201 + UUID v7 integration_id.
AC2  Response NEVER contains the plaintext/ciphertext auth_header — masked only.
AC8  List shows name/base_url/last_used.
RLS  Cross-tenant read is empty (AD-2).
Authz: non-builder POST -> 403; delete is symmetric with create (no asymmetry).
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.integration.conftest import login_token

INTEGRATION_PAYLOAD = {
    "name": "Demo Gmail",
    "base_url": "https://stub.example.com/gmail",
    "auth_header": "Bearer super-secret-token-abcd1234",
    "schema": {"type": "object", "properties": {}},
}


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_agent(client: TestClient, token: str, *, department_id: str) -> dict[str, Any]:
    r = client.post(
        "/agents",
        json={
            "name": "Integrations Agent",
            "department_id": department_id,
            "system_prompt": "You are helpful.",
        },
        headers=_auth_headers(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]


# ---------------------------------------------------------------------------
# AC1 — register
# ---------------------------------------------------------------------------

def test_create_integration_returns_201_with_uuid_v7_id(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))

    r = agent_client.post(
        f"/agents/{agent['id']}/integrations",
        json=INTEGRATION_PAYLOAD,
        headers=_auth_headers(token),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["agent_id"] == agent["id"]
    assert data["name"] == "Demo Gmail"
    assert data["id"][14] == "7"  # UUID v7 version nibble


def test_create_integration_response_never_contains_full_header(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))

    r = agent_client.post(
        f"/agents/{agent['id']}/integrations",
        json=INTEGRATION_PAYLOAD,
        headers=_auth_headers(token),
    )
    data = r.json()["data"]
    raw_body = r.text
    assert "super-secret-token-abcd1234" not in raw_body
    assert "auth_header" not in data
    assert data["auth_header_masked"].startswith("Bearer ••••")
    assert data["auth_header_masked"].endswith("1234")


def test_create_integration_forbidden_for_non_owner_non_dept(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))

    other_token = login_token(agent_client, "builder2@tenantc.example")
    r = agent_client.post(
        f"/agents/{agent['id']}/integrations",
        json=INTEGRATION_PAYLOAD,
        headers=_auth_headers(other_token),
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# AC8 — list / RLS
# ---------------------------------------------------------------------------

def test_list_integrations_shows_name_base_url_last_used(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))
    agent_client.post(
        f"/agents/{agent['id']}/integrations",
        json=INTEGRATION_PAYLOAD,
        headers=_auth_headers(token),
    )

    r = agent_client.get(f"/agents/{agent['id']}/integrations", headers=_auth_headers(token))
    assert r.status_code == 200
    integrations = r.json()["data"]
    assert len(integrations) == 1
    row = integrations[0]
    assert row["name"] == "Demo Gmail"
    assert row["base_url"] == "https://stub.example.com/gmail"
    assert row["last_used_at"] is None


def test_cross_tenant_list_is_empty(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    """RLS: a Tenant B user sees no Tenant C integrations (AD-2)."""
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))
    agent_client.post(
        f"/agents/{agent['id']}/integrations",
        json=INTEGRATION_PAYLOAD,
        headers=_auth_headers(token),
    )

    bob_token = login_token(agent_client, "bob@tenantb.example")
    r = agent_client.get(f"/agents/{agent['id']}/integrations", headers=_auth_headers(bob_token))
    assert r.status_code == 200
    assert r.json()["data"] == []


# ---------------------------------------------------------------------------
# Update / soft-delete (symmetric authz)
# ---------------------------------------------------------------------------

def test_patch_integration_updates_name(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))
    created = agent_client.post(
        f"/agents/{agent['id']}/integrations",
        json=INTEGRATION_PAYLOAD,
        headers=_auth_headers(token),
    ).json()["data"]

    r = agent_client.patch(
        f"/agents/{agent['id']}/integrations/{created['id']}",
        json={"name": "Demo Gmail v2"},
        headers=_auth_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "Demo Gmail v2"


def test_delete_integration_soft_deletes_and_excludes_from_list(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))
    created = agent_client.post(
        f"/agents/{agent['id']}/integrations",
        json=INTEGRATION_PAYLOAD,
        headers=_auth_headers(token),
    ).json()["data"]

    r = agent_client.delete(
        f"/agents/{agent['id']}/integrations/{created['id']}", headers=_auth_headers(token)
    )
    assert r.status_code == 200

    r_list = agent_client.get(f"/agents/{agent['id']}/integrations", headers=_auth_headers(token))
    assert r_list.json()["data"] == []


def test_delete_integration_forbidden_for_non_owner_non_dept(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    """Symmetric authz — delete must match create authz (no asymmetry, Story 2.4 bug fixed)."""
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))
    created = agent_client.post(
        f"/agents/{agent['id']}/integrations",
        json=INTEGRATION_PAYLOAD,
        headers=_auth_headers(token),
    ).json()["data"]

    other_token = login_token(agent_client, "builder2@tenantc.example")
    r = agent_client.delete(
        f"/agents/{agent['id']}/integrations/{created['id']}", headers=_auth_headers(other_token)
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# AC9 — Test Integration
# ---------------------------------------------------------------------------

def test_test_integration_endpoint_reports_status_without_header(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))
    # Loopback port with no listener -- fails fast, no external DNS/network dependency.
    created = agent_client.post(
        f"/agents/{agent['id']}/integrations",
        json={**INTEGRATION_PAYLOAD, "base_url": "http://127.0.0.1:1"},
        headers=_auth_headers(token),
    ).json()["data"]

    r = agent_client.post(
        f"/agents/{agent['id']}/integrations/{created['id']}/test", headers=_auth_headers(token)
    )
    assert r.status_code == 200
    result = r.json()["data"]
    assert result["status"] == "disconnected"
    assert "super-secret-token-abcd1234" not in r.text
    assert set(result.keys()) == {"status", "status_code", "latency_ms"}
