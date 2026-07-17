"""T8.4 — AC6: every upload/delete emits exactly one audit_trail row.

Asserts `type` in {kb.document.uploaded, kb.document.deleted} and that
`input`/`output` never carry document bytes/text (NFR-9) — metadata only.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import AdminSessionLocal
from tests.integration.conftest import login_token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_agent(client: TestClient, token: str, *, department_id: str) -> dict[str, Any]:
    r = client.post(
        "/agents",
        json={
            "name": "Audit KB Agent",
            "department_id": department_id,
            "system_prompt": "You are helpful.",
        },
        headers=_auth_headers(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _audit_rows(document_id: str, entry_type: str) -> list[dict]:
    with AdminSessionLocal() as s:
        rows = s.execute(
            text(
                "SELECT input, output FROM audit_trail "
                "WHERE type = :t AND input->>'document_id' = :did"
            ),
            {"t": entry_type, "did": document_id},
        ).fetchall()
    return [{"input": r[0], "output": r[1]} for r in rows]


def test_upload_emits_exactly_one_kb_document_uploaded_row(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(
        agent_client, token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    created = agent_client.post(
        f"/agents/{agent['id']}/kb/documents",
        files={"file": ("audited.txt", b"policy text content", "text/plain")},
        headers=_auth_headers(token),
    ).json()["data"]

    rows = _audit_rows(created["id"], "kb.document.uploaded")
    assert len(rows) == 1
    payload = rows[0]
    assert payload["input"]["filename"] == "audited.txt"
    assert payload["input"]["agent_id"] == agent["id"]
    # NFR-9 — never document bytes/extracted text.
    assert "policy text content" not in str(payload["input"])
    assert "policy text content" not in str(payload["output"])
    assert "data" not in payload["input"]
    assert "content" not in payload["input"]


def test_delete_emits_exactly_one_kb_document_deleted_row(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(
        agent_client, token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    created = agent_client.post(
        f"/agents/{agent['id']}/kb/documents",
        files={"file": ("todelete-audit.txt", b"secret sop content", "text/plain")},
        headers=_auth_headers(token),
    ).json()["data"]

    r = agent_client.delete(
        f"/agents/{agent['id']}/kb/documents/{created['id']}", headers=_auth_headers(token)
    )
    assert r.status_code == 200

    rows = _audit_rows(created["id"], "kb.document.deleted")
    assert len(rows) == 1
    assert "secret sop content" not in str(rows[0]["input"])
    assert "secret sop content" not in str(rows[0]["output"])
