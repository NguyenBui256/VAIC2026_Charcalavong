"""T7.6 — /agents/{id}/tools API: register/list/patch/delete + Test Tool.

AC1  POST returns 201 + UUID v7 tool_id; invalid schema -> structured error;
     header/auth not echoed in full.
AC7  POST .../test returns a structured ToolOutput.

Uses fakes for SandboxPort/McpClientPort/AuditPort where the test only
checks routing/shape -- no real MCP server, no real subprocess needed here
(real-subprocess coverage lives in tests/unit/test_sandbox.py).
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.integration.conftest import login_token

MCP_SCHEMA_TOOL = {
    "display_name": "rag.search",
    "header": {"auth": {"type": "bearer", "token_ref": "vault://kb-token"}},
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
    "output_schema": {
        "type": "object",
        "properties": {"passages": {"type": "array"}},
        "required": ["passages"],
    },
}


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_agent(client: TestClient, token: str, *, department_id: str) -> dict[str, Any]:
    r = client.post(
        "/agents",
        json={
            "name": "Tools Agent",
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

def test_create_tool_returns_201_with_uuid_v7_tool_id(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))

    r = agent_client.post(
        f"/agents/{agent['id']}/tools", json=MCP_SCHEMA_TOOL, headers=_auth_headers(token)
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["agent_id"] == agent["id"]
    assert data["display_name"] == "rag.search"
    # UUID v7 -> version nibble is '7'.
    assert data["id"][14] == "7"


def test_create_tool_header_not_echoed_in_full(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))

    r = agent_client.post(
        f"/agents/{agent['id']}/tools", json=MCP_SCHEMA_TOOL, headers=_auth_headers(token)
    )
    data = r.json()["data"]
    assert "vault://kb-token" not in str(data["header"])
    assert data["header"] == {"auth": True}


def test_create_tool_invalid_schema_returns_structured_error(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))

    bad_payload = {**MCP_SCHEMA_TOOL, "input_schema": {"type": "not-a-real-type"}}
    r = agent_client.post(
        f"/agents/{agent['id']}/tools", json=bad_payload, headers=_auth_headers(token)
    )
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "invalid_schema"


def test_create_tool_forbidden_for_non_owner_non_dept(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))

    other_token = login_token(agent_client, "builder2@tenantc.example")
    r = agent_client.post(
        f"/agents/{agent['id']}/tools", json=MCP_SCHEMA_TOOL, headers=_auth_headers(other_token)
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# List / patch / delete
# ---------------------------------------------------------------------------

def test_list_tools_returns_registered_tools(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))
    agent_client.post(
        f"/agents/{agent['id']}/tools", json=MCP_SCHEMA_TOOL, headers=_auth_headers(token)
    )

    r = agent_client.get(f"/agents/{agent['id']}/tools", headers=_auth_headers(token))
    assert r.status_code == 200
    tools = r.json()["data"]
    assert len(tools) == 1
    assert tools[0]["kind"] == "mcp"


def test_patch_tool_updates_display_name(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))
    created = agent_client.post(
        f"/agents/{agent['id']}/tools", json=MCP_SCHEMA_TOOL, headers=_auth_headers(token)
    ).json()["data"]

    r = agent_client.patch(
        f"/agents/{agent['id']}/tools/{created['id']}",
        json={"display_name": "rag.search.v2"},
        headers=_auth_headers(token),
    )
    assert r.status_code == 200
    assert r.json()["data"]["display_name"] == "rag.search.v2"


def test_delete_tool_soft_deletes(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))
    created = agent_client.post(
        f"/agents/{agent['id']}/tools", json=MCP_SCHEMA_TOOL, headers=_auth_headers(token)
    ).json()["data"]

    r = agent_client.delete(
        f"/agents/{agent['id']}/tools/{created['id']}", headers=_auth_headers(token)
    )
    assert r.status_code == 200

    r_list = agent_client.get(f"/agents/{agent['id']}/tools", headers=_auth_headers(token))
    assert r_list.json()["data"] == []


def test_delete_tool_forbidden_for_non_owner_non_dept(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    """AD-11 parity — delete authz must match create authz (no asymmetry)."""
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))
    created = agent_client.post(
        f"/agents/{agent['id']}/tools", json=MCP_SCHEMA_TOOL, headers=_auth_headers(token)
    ).json()["data"]

    other_token = login_token(agent_client, "builder2@tenantc.example")
    r = agent_client.delete(
        f"/agents/{agent['id']}/tools/{created['id']}", headers=_auth_headers(other_token)
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# AC7 — Test Tool
# ---------------------------------------------------------------------------

def test_test_tool_input_mismatch_returns_structured_error(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))
    created = agent_client.post(
        f"/agents/{agent['id']}/tools", json=MCP_SCHEMA_TOOL, headers=_auth_headers(token)
    ).json()["data"]

    r = agent_client.post(
        f"/agents/{agent['id']}/tools/{created['id']}/test",
        json={"sample_input": {}},  # missing required "query"
        headers=_auth_headers(token),
    )
    assert r.status_code == 200
    result = r.json()["data"]
    assert result["success"] is False
    assert "Input validation failed" in result["error"]


def test_test_tool_embedded_python_success(
    agent_client: TestClient, agent_seed_data: dict[str, Any]
) -> None:
    token = login_token(agent_client, "builder@tenantc.example")
    agent = _create_agent(agent_client, token, department_id=str(agent_seed_data["dept_agents_id"]))

    payload = {
        "display_name": "double_it",
        "header": {},
        "input_schema": {
            "type": "object",
            "properties": {"n": {"type": "number"}},
            "required": ["n"],
        },
        "output_schema": {
            "type": "object",
            "properties": {"doubled": {"type": "number"}},
            "required": ["doubled"],
        },
        "embedded_python": (
            "import sys, json\n"
            "data = json.loads(sys.stdin.read())\n"
            "print(json.dumps({'doubled': data['n'] * 2}))\n"
        ),
    }
    created = agent_client.post(
        f"/agents/{agent['id']}/tools", json=payload, headers=_auth_headers(token)
    ).json()["data"]

    r = agent_client.post(
        f"/agents/{agent['id']}/tools/{created['id']}/test",
        json={"sample_input": {"n": 21}},
        headers=_auth_headers(token),
    )
    assert r.status_code == 200, r.text
    result = r.json()["data"]
    assert result["success"] is True
    assert result["output"] == {"doubled": 42}
