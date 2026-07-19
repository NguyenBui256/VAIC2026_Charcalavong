"""T8.1 — McpClientStub: successful ingest/delete, AD-11 pre-network raise."""

from __future__ import annotations

import uuid

import pytest

from app.core.adapters.mcp_client_stub import McpClientStub
from app.core.errors import AuthorizationError


def _stub(dept_id: uuid.UUID | None = None) -> McpClientStub:
    return McpClientStub(agent_department_id=dept_id or uuid.uuid4())


@pytest.mark.asyncio
async def test_rag_ingest_returns_success_with_document_id_and_chunk_count() -> None:
    dept_id = uuid.uuid4()
    stub = _stub(dept_id)
    result = await stub.call_tool(
        "rag.ingest",
        {
            "agent_id": "a",
            "filename": "f.pdf",
            "content_type": "application/pdf",
            "data": "x" * 5000,
        },
        tenant_id=uuid.uuid4(),
        department_id=dept_id,
    )
    assert result.success is True
    assert result.output["document_id"]
    assert result.output["chunk_count"] >= 1


@pytest.mark.asyncio
async def test_rag_delete_returns_success() -> None:
    dept_id = uuid.uuid4()
    stub = _stub(dept_id)
    result = await stub.call_tool(
        "rag.delete",
        {"external_document_id": "doc-1", "agent_id": "a"},
        tenant_id=uuid.uuid4(),
        department_id=dept_id,
    )
    assert result.success is True
    assert result.output == {"deleted": True}


@pytest.mark.asyncio
async def test_department_mismatch_raises_authorization_error_before_dispatch() -> None:
    """AD-11 — mismatch raises BEFORE any (simulated) network call."""
    agent_dept = uuid.uuid4()
    wrong_dept = uuid.uuid4()
    stub = _stub(agent_dept)
    with pytest.raises(AuthorizationError):
        await stub.call_tool(
            "rag.ingest",
            {"data": b""},
            tenant_id=uuid.uuid4(),
            department_id=wrong_dept,
        )


@pytest.mark.asyncio
async def test_list_tools_returns_stubbed_tool_names() -> None:
    dept_id = uuid.uuid4()
    stub = _stub(dept_id)
    tools = await stub.list_tools(tenant_id=uuid.uuid4(), department_id=dept_id)
    assert "rag.ingest" in tools
    assert "rag.delete" in tools
    assert "rag.search" in tools


@pytest.mark.asyncio
async def test_list_tools_department_mismatch_raises() -> None:
    stub = _stub(uuid.uuid4())
    with pytest.raises(AuthorizationError):
        await stub.list_tools(tenant_id=uuid.uuid4(), department_id=uuid.uuid4())
