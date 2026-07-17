"""GET /departments — tenant-scoped Department listing (Story 2.8 item #2).

Consumed by the Agent Builder Identity-tab dropdown and the Agent-list
Department filter (replaces the mocked wiring from Story 2.2).
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.integration.conftest import login_token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_get_departments_returns_tenant_scoped_list(
    api_client: TestClient, auth_seed: dict[str, Any]
) -> None:
    """Tenant A's caller sees Tenant A's Department(s) only, not Tenant B's."""
    token = login_token(api_client, "alice@tenanta.example")
    r = api_client.get("/departments", headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["error"] is None
    names = {d["name"] for d in body["data"]}
    assert "Credit" in names  # dept_a_id / Tenant A (seed_data)
    assert "HR" not in names  # dept_b_id / Tenant B — must not leak


def test_get_departments_cross_tenant_is_empty_of_other_tenant_rows(
    api_client: TestClient, auth_seed: dict[str, Any]
) -> None:
    """Tenant B's caller never sees Tenant A's Department rows (RLS)."""
    token = login_token(api_client, "bob@tenantb.example")
    r = api_client.get("/departments", headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    names = {d["name"] for d in r.json()["data"]}
    assert "HR" in names
    assert "Credit" not in names


def test_get_departments_requires_auth(api_client: TestClient) -> None:
    r = api_client.get("/departments")
    assert r.status_code == 401
