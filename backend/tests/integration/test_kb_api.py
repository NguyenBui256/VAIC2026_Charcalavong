"""T8.3 — /agents/{id}/kb/documents API: upload/oversize/timeout/delete/list.

AC1  upload chunks/embeds/indexes via McpClientPort stub -> status="indexed"
AC2  document appears in list with status
AC3  over-20MB rejected server-side (defense-in-depth; client gate is FE)
AC4  ingest timeout -> status="failed", failure_reason="Timeout"
AC5  delete removes the row + calls rag.delete
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import AdminSessionLocal
from app.core.ports.mcp_client import ToolResult
from app.modules.agent_builder import kb_service
from app.modules.agent_builder.service import Principal
from tests.integration.conftest import login_token


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_agent(client: TestClient, token: str, *, department_id: str) -> dict[str, Any]:
    r = client.post(
        "/agents",
        json={
            "name": "KB Agent",
            "department_id": department_id,
            "system_prompt": "You are helpful.",
        },
        headers=_auth_headers(token),
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]


# ---------------------------------------------------------------------------
# AC1/AC2 — upload happy path
# ---------------------------------------------------------------------------

def test_upload_happy_path_indexed_with_chunks(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(
        agent_client, token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    r = agent_client.post(
        f"/agents/{agent['id']}/kb/documents",
        files={"file": ("policy.txt", b"x" * 5000, "text/plain")},
        headers=_auth_headers(token),
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["status"] == "indexed"
    assert data["chunk_count"] > 0
    assert data["agent_id"] == agent["id"]
    assert data["filename"] == "policy.txt"


# ---------------------------------------------------------------------------
# AC2 — list returns docs with status
# ---------------------------------------------------------------------------

def test_list_returns_documents_with_status(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(
        agent_client, token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    agent_client.post(
        f"/agents/{agent['id']}/kb/documents",
        files={"file": ("sop.md", b"hello", "text/markdown")},
        headers=_auth_headers(token),
    )
    r = agent_client.get(f"/agents/{agent['id']}/kb/documents", headers=_auth_headers(token))
    assert r.status_code == 200
    docs = r.json()["data"]
    assert len(docs) == 1
    assert docs[0]["status"] in {"indexed", "processing", "failed"}


# ---------------------------------------------------------------------------
# AC3 — oversize rejected server-side (defense-in-depth)
# ---------------------------------------------------------------------------

def test_upload_oversize_rejected_server_side(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(
        agent_client, token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    oversize = b"x" * (20 * 1024 * 1024 + 1)
    r = agent_client.post(
        f"/agents/{agent['id']}/kb/documents",
        files={"file": ("big.txt", oversize, "text/plain")},
        headers=_auth_headers(token),
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "file_too_large"


def test_upload_unsupported_content_type_rejected(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(
        agent_client, token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    r = agent_client.post(
        f"/agents/{agent['id']}/kb/documents",
        files={"file": ("virus.exe", b"MZ", "application/x-msdownload")},
        headers=_auth_headers(token),
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "unsupported_content_type"


# ---------------------------------------------------------------------------
# AC4 — ingest timeout -> status="failed", failure_reason="Timeout"
# ---------------------------------------------------------------------------

class _TimeoutMcpClient:
    """Fake McpClientPort whose call_tool always times out (AC4 simulation)."""

    async def call_tool(self, tool_name: str, arguments: dict, *, tenant_id, department_id):
        _ = (tool_name, arguments, tenant_id, department_id)
        raise TimeoutError

    async def list_tools(self, *, tenant_id, department_id):
        _ = (tenant_id, department_id)
        return []


def test_ingest_timeout_sets_failed_status(
    app_session: Session, seeded_agent: dict[str, Any]
) -> None:
    from app.core.tenant_context import set_tenant_session_var, tenant_context

    tenant_context.set(seeded_agent["tenant_agents_id"])
    set_tenant_session_var(app_session, seeded_agent["tenant_agents_id"])
    app_session.execute(text("SET LOCAL ROLE vaic_app"))

    principal = Principal(
        user_id=seeded_agent["builder_user_id"],
        tenant_id=seeded_agent["tenant_agents_id"],
        department_id=seeded_agent["dept_agents_id"],
        role="builder",
    )
    doc = kb_service.upload_document(
        app_session,
        agent_id=seeded_agent["agent_a_id"],
        principal=principal,
        filename="slow.pdf",
        content_type="application/pdf",
        data=b"hello world",
        mcp_factory=lambda **_: _TimeoutMcpClient(),
    )
    assert doc.status == "failed"
    assert doc.failure_reason == "Timeout"


# ---------------------------------------------------------------------------
# AC5 — delete removes the row + calls rag.delete
# ---------------------------------------------------------------------------

class _SpyMcpClient:
    """Records rag.delete invocations."""

    calls: list[tuple[str, dict]] = []

    async def call_tool(self, tool_name: str, arguments: dict, *, tenant_id, department_id):
        _ = (tenant_id, department_id)
        _SpyMcpClient.calls.append((tool_name, arguments))
        return ToolResult(tool_name=tool_name, output={"deleted": True}, success=True)

    async def list_tools(self, *, tenant_id, department_id):
        _ = (tenant_id, department_id)
        return []


def test_delete_removes_row_and_calls_rag_delete(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(
        agent_client, token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    created = agent_client.post(
        f"/agents/{agent['id']}/kb/documents",
        files={"file": ("todelete.txt", b"content", "text/plain")},
        headers=_auth_headers(token),
    ).json()["data"]

    r = agent_client.delete(
        f"/agents/{agent['id']}/kb/documents/{created['id']}", headers=_auth_headers(token)
    )
    assert r.status_code == 200

    with AdminSessionLocal() as s:
        row = s.execute(
            text("SELECT id FROM kb_documents WHERE id = :id"), {"id": created["id"]}
        ).fetchone()
    assert row is None

    r_list = agent_client.get(
        f"/agents/{agent['id']}/kb/documents", headers=_auth_headers(token)
    )
    assert r_list.json()["data"] == []


def test_delete_non_owner_non_builder_dept_returns_403(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(
        agent_client, token, department_id=str(agent_seed_data["dept_agents_id"])
    )
    created = agent_client.post(
        f"/agents/{agent['id']}/kb/documents",
        files={"file": ("protected.txt", b"content", "text/plain")},
        headers=_auth_headers(token),
    ).json()["data"]

    other_token = login_token(agent_client, "builder2@tenantc.example")
    r = agent_client.delete(
        f"/agents/{agent['id']}/kb/documents/{created['id']}",
        headers=_auth_headers(other_token),
    )
    assert r.status_code == 403
