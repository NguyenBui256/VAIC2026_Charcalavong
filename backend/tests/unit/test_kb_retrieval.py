"""T1 -- kb_search: payload construction, pre-network AD-11 raise,
cross-department empty result, audit logging (Story 2.5)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

from app.core.errors import AuthorizationError
from app.core.ports.mcp_client import ToolResult
from app.modules.agent_builder.kb_retrieval import kb_search


@dataclass
class _FakeAgent:
    id: uuid.UUID
    tenant_id: uuid.UUID
    department_id: uuid.UUID


class _FakeAudit:
    """Records every `log()` call -- exercises the AuditPort contract."""

    def __init__(self) -> None:
        self.entries: list = []

    def log(self, entry) -> None:  # noqa: ANN001
        self.entries.append(entry)


class _RecordingMcpClient:
    """Captures the exact `call_tool` invocation for payload assertions."""

    def __init__(
        self, *, agent_department_id: uuid.UUID, passages: list[dict] | None = None
    ) -> None:
        self.agent_department_id = agent_department_id
        self._passages = passages or []
        self.calls: list[dict] = []

    async def call_tool(self, tool_name, arguments, *, tenant_id, department_id):  # noqa: ANN001
        self.calls.append(
            {
                "tool_name": tool_name,
                "arguments": arguments,
                "tenant_id": tenant_id,
                "department_id": department_id,
            }
        )
        return ToolResult(
            tool_name=tool_name, output={"passages": self._passages}, success=True
        )

    async def list_tools(self, *, tenant_id, department_id):  # noqa: ANN001
        return ["rag.search"]


class _MismatchMcpClient:
    """Mirrors `McpClientStub`'s AD-11 pre-network raise (Story 2.4 pattern).

    Raises BEFORE simulating any network dispatch -- `network_dispatched`
    stays `False` when the scope check fails, proving the raise happens
    before the "network" step, not after a swallowed/retried call.
    """

    def __init__(self, *, agent_department_id: uuid.UUID) -> None:
        self._dept = agent_department_id
        self.network_dispatched = False

    async def call_tool(self, tool_name, arguments, *, tenant_id, department_id):  # noqa: ANN001
        if department_id != self._dept:
            raise AuthorizationError(
                "department_id mismatch (AD-11)", code="mcp_scope_mismatch"
            )
        self.network_dispatched = True
        return ToolResult(tool_name=tool_name, output={"passages": []}, success=True)

    async def list_tools(self, *, tenant_id, department_id):  # noqa: ANN001
        return []


class _DepartmentScopedMcpClient:
    """Mimics an MCP index scoped by department -- returns `[]` for a scope
    with no indexed documents, never another department's documents (FR-2).
    """

    def __init__(
        self, *, agent_department_id: uuid.UUID, docs_by_department: dict
    ) -> None:
        self._dept = agent_department_id
        self._docs = docs_by_department

    async def call_tool(self, tool_name, arguments, *, tenant_id, department_id):  # noqa: ANN001
        if department_id != self._dept:
            raise AuthorizationError("mismatch", code="mcp_scope_mismatch")
        passages = self._docs.get(department_id, [])
        return ToolResult(tool_name=tool_name, output={"passages": passages}, success=True)

    async def list_tools(self, *, tenant_id, department_id):  # noqa: ANN001
        return []


def _agent(dept_id: uuid.UUID | None = None) -> _FakeAgent:
    return _FakeAgent(
        id=uuid.uuid4(), tenant_id=uuid.uuid4(), department_id=dept_id or uuid.uuid4()
    )


# -- AC1, AC3: payload shape + result mapping --------------------------------


@pytest.mark.asyncio
async def test_kb_search_builds_correct_call_tool_payload_and_maps_results() -> None:
    dept_id = uuid.uuid4()
    agent = _agent(dept_id)
    mcp = _RecordingMcpClient(
        agent_department_id=dept_id,
        passages=[
            {
                "passage": "Policy text",
                "document_name": "policy.pdf",
                "chunk_reference": "p1",
                "score": 0.87,
            },
        ],
    )
    audit = _FakeAudit()

    result = await kb_search(
        object(),
        agent.id,
        "What is the leave policy?",
        mcp_factory=lambda **kw: mcp,
        audit=audit,
        agent_loader=lambda session, aid: agent,
    )

    assert len(mcp.calls) == 1
    call = mcp.calls[0]
    assert call["tool_name"] == "rag.search"
    assert call["arguments"] == {
        "agent_id": str(agent.id),
        "query": "What is the leave policy?",
        "tenant_id": str(agent.tenant_id),
        "department_id": str(agent.department_id),
    }
    assert call["tenant_id"] == agent.tenant_id
    assert call["department_id"] == agent.department_id

    assert len(result) == 1
    assert result[0].passage == "Policy text"
    assert result[0].document_name == "policy.pdf"
    assert result[0].chunk_reference == "p1"
    assert result[0].score == 0.87


# -- AC2: department mismatch raises before any network dispatch ------------


@pytest.mark.asyncio
async def test_department_mismatch_raises_before_network_dispatch() -> None:
    """AC2 -- AD-11 mismatch propagates before the network; never swallowed."""
    real_dept = uuid.uuid4()
    other_dept = uuid.uuid4()
    agent = _agent(real_dept)
    # A misconfigured/mismatched MCP client instance (AD-11 enforcement lives
    # in the McpClientPort implementation itself, mirroring McpClientStub).
    mcp = _MismatchMcpClient(agent_department_id=other_dept)
    audit = _FakeAudit()

    with pytest.raises(AuthorizationError):
        await kb_search(
            object(),
            agent.id,
            "q",
            mcp_factory=lambda **kw: mcp,
            audit=audit,
            agent_loader=lambda session, aid: agent,
        )

    assert mcp.network_dispatched is False
    assert audit.entries == []  # a raised retrieval is never audited as complete


# -- AC4/FR-2: cross-department retrieval is empty, never another dept's docs


@pytest.mark.asyncio
async def test_cross_department_retrieval_returns_empty_never_other_department_docs() -> None:
    """AC4/FR-2 -- Credit Agent querying an HR-only-indexed KB gets []."""
    credit_dept = uuid.uuid4()
    hr_dept = uuid.uuid4()
    credit_agent = _agent(credit_dept)

    docs_by_department = {
        hr_dept: [
            {
                "passage": "HR leave policy",
                "document_name": "hr_policy.pdf",
                "chunk_reference": "p1",
                "score": 0.9,
            },
        ],
    }
    mcp = _DepartmentScopedMcpClient(
        agent_department_id=credit_dept, docs_by_department=docs_by_department
    )
    audit = _FakeAudit()

    result = await kb_search(
        object(),
        credit_agent.id,
        "What is the leave policy?",
        mcp_factory=lambda **kw: mcp,
        audit=audit,
        agent_loader=lambda session, aid: credit_agent,
    )

    assert result == []
    assert not any("hr" in p.document_name.lower() for p in result)


# -- AC5: audit.log() called exactly once with aggregated output ------------


@pytest.mark.asyncio
async def test_audit_logs_once_with_passage_count_and_top_score() -> None:
    dept_id = uuid.uuid4()
    agent = _agent(dept_id)
    mcp = _RecordingMcpClient(
        agent_department_id=dept_id,
        passages=[
            {"passage": "a", "document_name": "d1", "chunk_reference": "c1", "score": 0.5},
            {"passage": "b", "document_name": "d2", "chunk_reference": "c2", "score": 0.9},
        ],
    )
    audit = _FakeAudit()

    await kb_search(
        object(),
        agent.id,
        "leave policy",
        mcp_factory=lambda **kw: mcp,
        audit=audit,
        agent_loader=lambda session, aid: agent,
    )

    assert len(audit.entries) == 1
    entry = audit.entries[0]
    assert entry.type == "kb.retrieval"
    assert entry.input == {"agent_id": str(agent.id), "query": "leave policy"}
    assert entry.output == {"passage_count": 2, "top_score": 0.9}


@pytest.mark.asyncio
async def test_audit_logs_zero_passage_count_and_null_top_score_when_empty() -> None:
    dept_id = uuid.uuid4()
    agent = _agent(dept_id)
    mcp = _RecordingMcpClient(agent_department_id=dept_id, passages=[])
    audit = _FakeAudit()

    await kb_search(
        object(),
        agent.id,
        "q",
        mcp_factory=lambda **kw: mcp,
        audit=audit,
        agent_loader=lambda session, aid: agent,
    )

    assert len(audit.entries) == 1
    entry = audit.entries[0]
    assert entry.output == {"passage_count": 0, "top_score": None}
