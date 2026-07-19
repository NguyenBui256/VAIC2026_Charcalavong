"""T1 -- kb_search: payload construction, pre-network AD-11 raise,
cross-department empty result, audit logging (Story 2.5).

kb_search has a "two-gate" design (rag tool ref + granted doc ids) plus a
platform-id -> external-id translation step, all resolved via helpers that
are imported *inside* the function body:
  - app.modules.agent_builder.tool_catalog_service.list_agent_tool_refs
  - app.modules.agent_builder.agent_kb_service.list_agent_document_ids
  - session.execute(select(KbDocument.external_document_id)...) for the
    platform -> external id translation (falls back to platform ids as str
    when no external id has been recorded yet).

These tests patch those two helpers at their *source* modules (matching the
local `from ... import` inside kb_search) and supply a `_FakeSession` that
mimics `session.execute(...).scalars().all()` for the translation query.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest

from app.core.errors import AuthorizationError
from app.core.ports.mcp_client import ToolResult
from app.modules.agent_builder.kb_retrieval import kb_search


@dataclass
class _FakeAgent:
    id: uuid.UUID
    tenant_id: uuid.UUID
    department_id: uuid.UUID


@dataclass
class _FakeToolRef:
    """Stand-in for `Tool` rows returned by `list_agent_tool_refs`."""

    tool_type: str = "rag"


class _FakeAudit:
    """Records every `log()` call -- exercises the AuditPort contract."""

    def __init__(self) -> None:
        self.entries: list = []

    def log(self, entry) -> None:  # noqa: ANN001
        self.entries.append(entry)


class _FakeResult:
    """Mimics the SQLAlchemy `Result` returned by `session.execute(...)`."""

    def __init__(self, values: list) -> None:
        self._values = values

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list:
        return self._values


class _FakeSession:
    """Stand-in for `Session` -- only `execute()` is exercised by `kb_search`
    (the platform-id -> external-id translation query)."""

    def __init__(self, external_ids: list[str] | None = None) -> None:
        self._external_ids = external_ids if external_ids is not None else []

    def execute(self, _stmt) -> _FakeResult:  # noqa: ANN001
        return _FakeResult(self._external_ids)


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


def _patch_gates(
    monkeypatch: pytest.MonkeyPatch,
    *,
    has_rag: bool = True,
    platform_ids: list[uuid.UUID] | None = None,
) -> list[uuid.UUID]:
    """Patch the two-gate helpers (rag tool ref + granted doc ids) at their
    *source* modules -- `kb_search` imports them locally via `from ... import`
    on every call, so patching the source attribute is picked up correctly.

    Returns the `platform_ids` list used for gate 2, so callers can assert
    against it (e.g. the platform-id fallback path).
    """
    resolved_ids = platform_ids if platform_ids is not None else [uuid.uuid4()]
    tool_refs = [_FakeToolRef(tool_type="rag" if has_rag else "other")]

    monkeypatch.setattr(
        "app.modules.agent_builder.tool_catalog_service.list_agent_tool_refs",
        lambda session, *, agent_id: tool_refs,
    )
    monkeypatch.setattr(
        "app.modules.agent_builder.agent_kb_service.list_agent_document_ids",
        lambda session, agent_id: resolved_ids,
    )
    return resolved_ids


# -- AC1, AC3: payload shape + result mapping --------------------------------


@pytest.mark.asyncio
async def test_kb_search_builds_correct_call_tool_payload_and_maps_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dept_id = uuid.uuid4()
    agent = _agent(dept_id)
    external_ids = ["ext-doc-1"]
    platform_ids = _patch_gates(monkeypatch, platform_ids=[uuid.uuid4()])
    session = _FakeSession(external_ids=external_ids)
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
        session,
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
        "document_ids": external_ids,
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


# -- gate 3: platform id -> external id translation --------------------------


@pytest.mark.asyncio
async def test_kb_search_translates_platform_ids_to_external_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When `KbDocument.external_document_id` is set, `document_ids` in the
    `rag.search` payload uses the vaic_tools external ids, not the platform
    UUIDs."""
    dept_id = uuid.uuid4()
    agent = _agent(dept_id)
    _patch_gates(monkeypatch, platform_ids=[uuid.uuid4(), uuid.uuid4()])
    external_ids = ["vaic-ext-1", "vaic-ext-2"]
    session = _FakeSession(external_ids=external_ids)
    mcp = _RecordingMcpClient(agent_department_id=dept_id, passages=[])
    audit = _FakeAudit()

    await kb_search(
        session,
        agent.id,
        "q",
        mcp_factory=lambda **kw: mcp,
        audit=audit,
        agent_loader=lambda session, aid: agent,
    )

    assert mcp.calls[0]["arguments"]["document_ids"] == external_ids


@pytest.mark.asyncio
async def test_kb_search_falls_back_to_platform_ids_when_no_external_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no `KbDocument` row has `external_document_id` set (e.g. stub/test
    path, not yet ingested by vaic_tools), `document_ids` falls back to the
    stringified platform UUIDs."""
    dept_id = uuid.uuid4()
    agent = _agent(dept_id)
    platform_ids = _patch_gates(monkeypatch, platform_ids=[uuid.uuid4(), uuid.uuid4()])
    session = _FakeSession(external_ids=[])  # no external ids recorded yet
    mcp = _RecordingMcpClient(agent_department_id=dept_id, passages=[])
    audit = _FakeAudit()

    await kb_search(
        session,
        agent.id,
        "q",
        mcp_factory=lambda **kw: mcp,
        audit=audit,
        agent_loader=lambda session, aid: agent,
    )

    assert mcp.calls[0]["arguments"]["document_ids"] == [str(d) for d in platform_ids]


# -- AC2: department mismatch raises before any network dispatch ------------


@pytest.mark.asyncio
async def test_department_mismatch_raises_before_network_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC2 -- AD-11 mismatch propagates before the network; never swallowed."""
    real_dept = uuid.uuid4()
    other_dept = uuid.uuid4()
    agent = _agent(real_dept)
    _patch_gates(monkeypatch)
    session = _FakeSession(external_ids=["ext-1"])
    # A misconfigured/mismatched MCP client instance (AD-11 enforcement lives
    # in the McpClientPort implementation itself, mirroring McpClientStub).
    mcp = _MismatchMcpClient(agent_department_id=other_dept)
    audit = _FakeAudit()

    with pytest.raises(AuthorizationError):
        await kb_search(
            session,
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
async def test_cross_department_retrieval_returns_empty_never_other_department_docs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4/FR-2 -- Credit Agent querying an HR-only-indexed KB gets []."""
    credit_dept = uuid.uuid4()
    hr_dept = uuid.uuid4()
    credit_agent = _agent(credit_dept)
    _patch_gates(monkeypatch)
    session = _FakeSession(external_ids=["ext-1"])

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
        session,
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
async def test_audit_logs_once_with_passage_count_and_top_score(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dept_id = uuid.uuid4()
    agent = _agent(dept_id)
    _patch_gates(monkeypatch)
    session = _FakeSession(external_ids=["ext-1"])
    mcp = _RecordingMcpClient(
        agent_department_id=dept_id,
        passages=[
            {"passage": "a", "document_name": "d1", "chunk_reference": "c1", "score": 0.5},
            {"passage": "b", "document_name": "d2", "chunk_reference": "c2", "score": 0.9},
        ],
    )
    audit = _FakeAudit()

    await kb_search(
        session,
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
async def test_audit_logs_zero_passage_count_and_null_top_score_when_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dept_id = uuid.uuid4()
    agent = _agent(dept_id)
    _patch_gates(monkeypatch)
    session = _FakeSession(external_ids=["ext-1"])
    mcp = _RecordingMcpClient(agent_department_id=dept_id, passages=[])
    audit = _FakeAudit()

    await kb_search(
        session,
        agent.id,
        "q",
        mcp_factory=lambda **kw: mcp,
        audit=audit,
        agent_loader=lambda session, aid: agent,
    )

    assert len(audit.entries) == 1
    entry = audit.entries[0]
    assert entry.output == {"passage_count": 0, "top_score": None}
