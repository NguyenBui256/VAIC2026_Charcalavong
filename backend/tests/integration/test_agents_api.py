"""AC1–AC7, AC10 — /agents CRUD API tests (Story 2.1).

Test plan (AC # → test name):
- AC1  POST /agents creates a scoped Agent (201)
       -> test_post_agents_creates_scoped_agent_201
- AC2  GET /agents/{id} returns the same record
       -> test_get_agent_returns_same_record
- AC3  Cross-tenant read returns 404, not 403
       -> test_cross_tenant_get_returns_404_not_403
- AC4  List is tenant-scoped
       -> test_list_agents_is_tenant_scoped
- AC5  Department filter
       -> test_list_agents_department_filter
       -> test_list_agents_department_filter_cross_tenant_empty
- AC6  Authorization on PATCH
       -> test_patch_non_owner_non_builder_dept_returns_403
       -> test_patch_owner_allowed
       -> test_patch_builder_in_same_department_allowed
- AC7  DELETE is soft-delete only, same scoping
       -> test_delete_soft_deletes_and_excludes_from_list
- AC10 builder role required to create/mutate
       -> test_post_agents_non_builder_returns_403
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.integration.conftest import login_token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_agent(
    client: TestClient, token: str, *, department_id: str, name: str = "Support Bot"
) -> dict[str, Any]:
    r = client.post(
        "/agents",
        json={
            "name": name,
            "department_id": department_id,
            "system_prompt": "You are a helpful assistant.",
        },
        headers=_auth_headers(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]


# ---------------------------------------------------------------------------
# AC1 — POST /agents creates a scoped Agent (201)
# ---------------------------------------------------------------------------

def test_post_agents_creates_scoped_agent_201(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    data = _create_agent(
        agent_client, token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    assert data["tenant_id"] == str(agent_seed_data["tenant_agents_id"])
    assert data["department_id"] == str(agent_seed_data["dept_agents_id"])
    assert data["owner_id"] == str(agent_seed_data["builder_user_id"])
    assert data["version"] == 1
    assert "created_at" in data
    import uuid as _uuid

    parsed = _uuid.UUID(data["id"])
    assert parsed.version == 7


# ---------------------------------------------------------------------------
# AC10 — non-builder POST -> 403 FORBIDDEN
# ---------------------------------------------------------------------------

def test_post_agents_non_builder_returns_403(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "operator@tenantc.example")
    r = agent_client.post(
        "/agents",
        json={
            "name": "Nope",
            "department_id": str(agent_seed_data["dept_agents_id"]),
            "system_prompt": "x",
        },
        headers=_auth_headers(token),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# AC2 — GET /agents/{id} returns the same record
# ---------------------------------------------------------------------------

def test_get_agent_returns_same_record(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    created = _create_agent(
        agent_client, token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    r = agent_client.get(f"/agents/{created['id']}", headers=_auth_headers(token))
    assert r.status_code == 200
    assert r.json()["data"] == created


# ---------------------------------------------------------------------------
# AC3 — Cross-tenant read returns 404, not 403
# ---------------------------------------------------------------------------

def test_cross_tenant_get_returns_404_not_403(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    builder_token = login_token(agent_client, "builder@tenantc.example")
    created = _create_agent(
        agent_client, builder_token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    bob_token = login_token(agent_client, "bob@tenantb.example")
    r = agent_client.get(f"/agents/{created['id']}", headers=_auth_headers(bob_token))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


# ---------------------------------------------------------------------------
# AC4 — List is tenant-scoped
# ---------------------------------------------------------------------------

def test_list_agents_is_tenant_scoped(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    builder_token = login_token(agent_client, "builder@tenantc.example")
    _create_agent(
        agent_client,
        builder_token,
        department_id=str(agent_seed_data["dept_agents_id"]),
        name="TenantA-only Agent",
    )
    r = agent_client.get("/agents", headers=_auth_headers(builder_token))
    assert r.status_code == 200
    names = {a["name"] for a in r.json()["data"]}
    assert "TenantA-only Agent" in names

    bob_token = login_token(agent_client, "bob@tenantb.example")
    r2 = agent_client.get("/agents", headers=_auth_headers(bob_token))
    assert r2.status_code == 200
    names_b = {a["name"] for a in r2.json()["data"]}
    assert "TenantA-only Agent" not in names_b


# ---------------------------------------------------------------------------
# AC5 — Department filter
# ---------------------------------------------------------------------------

def test_list_agents_department_filter(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    builder_token = login_token(agent_client, "builder@tenantc.example")
    builder2_token = login_token(agent_client, "builder2@tenantc.example")
    _create_agent(
        agent_client,
        builder_token,
        department_id=str(agent_seed_data["dept_agents_id"]),
        name="Dept1 Agent",
    )
    _create_agent(
        agent_client,
        builder2_token,
        department_id=str(agent_seed_data["dept_agents2_id"]),
        name="Dept2 Agent",
    )
    r = agent_client.get(
        "/agents",
        params={"department_id": str(agent_seed_data["dept_agents_id"])},
        headers=_auth_headers(builder_token),
    )
    assert r.status_code == 200
    names = {a["name"] for a in r.json()["data"]}
    assert "Dept1 Agent" in names
    assert "Dept2 Agent" not in names


def test_list_agents_department_filter_cross_tenant_empty(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    """Cross-tenant departments yield an empty list (AC5)."""
    bob_token = login_token(agent_client, "bob@tenantb.example")
    r = agent_client.get(
        "/agents",
        params={"department_id": str(agent_seed_data["dept_agents_id"])},
        headers=_auth_headers(bob_token),
    )
    assert r.status_code == 200
    assert r.json()["data"] == []


# ---------------------------------------------------------------------------
# AC6 — Authorization on PATCH
# ---------------------------------------------------------------------------

def test_patch_non_owner_non_builder_dept_returns_403(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    builder_token = login_token(agent_client, "builder@tenantc.example")
    created = _create_agent(
        agent_client, builder_token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    # builder2 is a builder but in a DIFFERENT department, and not the owner.
    builder2_token = login_token(agent_client, "builder2@tenantc.example")
    r = agent_client.patch(
        f"/agents/{created['id']}",
        json={"name": "Hacked"},
        headers=_auth_headers(builder2_token),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


def test_patch_owner_allowed(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    builder_token = login_token(agent_client, "builder@tenantc.example")
    created = _create_agent(
        agent_client, builder_token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    r = agent_client.patch(
        f"/agents/{created['id']}",
        json={"name": "Renamed"},
        headers=_auth_headers(builder_token),
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["name"] == "Renamed"
    assert data["version"] == 2


def test_patch_builder_in_same_department_allowed(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    """A different builder in the SAME department as the Agent may PATCH."""
    builder_token = login_token(agent_client, "builder@tenantc.example")
    created = _create_agent(
        agent_client, builder_token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    # Log a second builder into dept_a via a fresh login using the same
    # department as the agent — reuse admin user "alice" upgraded is not
    # available, so promote operator temporarily is out of scope; instead
    # use builder_dept2_user relocated logically is not possible here, so
    # this case is covered by the same builder (owner) plus dept coverage
    # test above. We instead verify a builder in dept_a but NOT owner: reuse
    # builder token itself is owner, so exercise via direct service call.
    # Create a third user: builder role, same department (dept_a), not owner.
    import uuid as _uuid

    from sqlalchemy import text as _text

    from app.core.db import AdminSessionLocal

    third_id = _uuid.uuid4()
    with AdminSessionLocal() as s:
        s.execute(
            _text(
                "INSERT INTO users (id, tenant_id, department_id, email, role, "
                "password_hash, is_active) VALUES "
                "(:id, :tid, :did, :email, 'builder', :pwh, true)"
            ),
            {
                "id": str(third_id),
                "tid": str(agent_seed_data["tenant_agents_id"]),
                "did": str(agent_seed_data["dept_agents_id"]),
                "email": "builder3@tenantc.example",
                "pwh": _login_pw_hash(),
            },
        )
        s.commit()
    try:
        third_token = login_token(agent_client, "builder3@tenantc.example")
        r = agent_client.patch(
            f"/agents/{created['id']}",
            json={"name": "Team Renamed"},
            headers=_auth_headers(third_token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "Team Renamed"
    finally:
        with AdminSessionLocal() as s:
            s.execute(_text("DELETE FROM users WHERE id = :id"), {"id": str(third_id)})
            s.commit()


def _login_pw_hash() -> str:
    from tests.integration.conftest import _PWD, SEED_PASSWORD

    return _PWD.hash(SEED_PASSWORD)


# ---------------------------------------------------------------------------
# AC7 — DELETE is soft-delete only, same scoping as PATCH
# ---------------------------------------------------------------------------

def test_delete_soft_deletes_and_excludes_from_list(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    from sqlalchemy import text as _text

    from app.core.db import AdminSessionLocal

    builder_token = login_token(agent_client, "builder@tenantc.example")
    created = _create_agent(
        agent_client,
        builder_token,
        department_id=str(agent_seed_data["dept_agents_id"]),
        name="To Delete",
    )
    r = agent_client.delete(
        f"/agents/{created['id']}", headers=_auth_headers(builder_token)
    )
    assert r.status_code == 200

    # Excluded from list.
    r_list = agent_client.get("/agents", headers=_auth_headers(builder_token))
    names = {a["name"] for a in r_list.json()["data"]}
    assert "To Delete" not in names

    # Excluded from GET.
    r_get = agent_client.get(
        f"/agents/{created['id']}", headers=_auth_headers(builder_token)
    )
    assert r_get.status_code == 404

    # Row still present in DB (soft-delete, never hard delete).
    with AdminSessionLocal() as s:
        row = s.execute(
            _text("SELECT is_deleted, deleted_at FROM agents WHERE id = :id"),
            {"id": created["id"]},
        ).fetchone()
    assert row is not None
    assert row[0] is True
    assert row[1] is not None


def test_delete_non_owner_non_builder_dept_returns_403(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    builder_token = login_token(agent_client, "builder@tenantc.example")
    created = _create_agent(
        agent_client, builder_token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    builder2_token = login_token(agent_client, "builder2@tenantc.example")
    r = agent_client.delete(
        f"/agents/{created['id']}", headers=_auth_headers(builder2_token)
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"
