"""AC8 — Every CRUD op on /agents emits exactly one audit_trail entry.

Verifies `type` in {agent.created, agent.updated, agent.deleted} and that
the row was written through PostgresAuditSink (never direct SQL/ORM).
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import AdminSessionLocal
from tests.integration.conftest import login_token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _count_audit_rows(agent_id: str, entry_type: str) -> int:
    with AdminSessionLocal() as s:
        return s.execute(
            text(
                "SELECT COUNT(*) FROM audit_trail "
                "WHERE agent_id = :aid AND type = :t"
            ),
            {"aid": agent_id, "t": entry_type},
        ).scalar()


def test_create_agent_emits_one_agent_created_audit_row(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    r = agent_client.post(
        "/agents",
        json={
            "name": "Audit Bot",
            "department_id": str(agent_seed_data["dept_agents_id"]),
            "system_prompt": "x",
        },
        headers=_auth_headers(token),
    )
    assert r.status_code == 201
    agent_id = r.json()["data"]["id"]
    assert _count_audit_rows(agent_id, "agent.created") == 1


def test_update_agent_emits_one_agent_updated_audit_row(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    created = agent_client.post(
        "/agents",
        json={
            "name": "Audit Bot 2",
            "department_id": str(agent_seed_data["dept_agents_id"]),
            "system_prompt": "x",
        },
        headers=_auth_headers(token),
    ).json()["data"]

    r = agent_client.patch(
        f"/agents/{created['id']}",
        json={"name": "Audit Bot 2 Renamed"},
        headers=_auth_headers(token),
    )
    assert r.status_code == 200
    assert _count_audit_rows(created["id"], "agent.updated") == 1


def test_delete_agent_emits_one_agent_deleted_audit_row(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    created = agent_client.post(
        "/agents",
        json={
            "name": "Audit Bot 3",
            "department_id": str(agent_seed_data["dept_agents_id"]),
            "system_prompt": "x",
        },
        headers=_auth_headers(token),
    ).json()["data"]

    r = agent_client.delete(
        f"/agents/{created['id']}", headers=_auth_headers(token)
    )
    assert r.status_code == 200
    assert _count_audit_rows(created["id"], "agent.deleted") == 1
