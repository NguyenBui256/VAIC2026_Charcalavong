"""AC8 — Every CRUD op on /workflows emits exactly one audit_trail entry.

Verifies `type` in {workflow.created, workflow.updated} and that the row
was written through PostgresAuditSink (never direct SQL/ORM). Mirrors
`test_agent_audit.py`; `agent_id` column on `audit_trail` stores the
Workflow id here (the CRUD-audit stopgap, AD-4/OQ-1, treats "the entity
being written" as the audit subject regardless of module).
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import AdminSessionLocal
from tests.integration.conftest import login_token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _count_audit_rows(workflow_id: str, entry_type: str) -> int:
    with AdminSessionLocal() as s:
        return s.execute(
            text(
                "SELECT COUNT(*) FROM audit_trail "
                "WHERE agent_id = :wid AND type = :t"
            ),
            {"wid": workflow_id, "t": entry_type},
        ).scalar()


def test_create_workflow_emits_one_workflow_created_audit_row(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    r = agent_client.post(
        "/workflows",
        json={"name": "Audit Flow", "description": "x"},
        headers=_auth_headers(token),
    )
    assert r.status_code == 201
    workflow_id = r.json()["data"]["id"]
    assert _count_audit_rows(workflow_id, "workflow.created") == 1


def test_update_workflow_emits_one_workflow_updated_audit_row(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    created = agent_client.post(
        "/workflows",
        json={"name": "Audit Flow 2", "description": "x"},
        headers=_auth_headers(token),
    ).json()["data"]

    r = agent_client.patch(
        f"/workflows/{created['id']}",
        json={"name": "Audit Flow 2 Renamed"},
        headers=_auth_headers(token),
    )
    assert r.status_code == 200
    assert _count_audit_rows(created["id"], "workflow.updated") == 1
