"""Unit tests for `tool_service.invoke_tool` (Story 2.6 T7.2/T7.3, AC2-AC5).

Uses fakes for `AuditPort`, `SandboxPort`, `McpClientPort` -- no real
subprocess or network. Asserts the right port is called (and the *other*
one is NOT called) for each branch, and that every outcome emits exactly
one audit entry of the correct `type`.
"""

from __future__ import annotations

import uuid

from app.core.ports.audit import AuditEntry
from app.core.ports.mcp_client import ToolResult
from app.core.ports.sandbox import SandboxResult
from app.modules.agent_builder.models import Tool
from app.modules.agent_builder.tool_service import invoke_tool

TENANT_ID = uuid.uuid4()
DEPT_ID = uuid.uuid4()


class FakeAudit:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def log(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


class FakeSandbox:
    def __init__(self, result: SandboxResult) -> None:
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def run(self, code: str, stdin: str = "", *, timeout_s: int = 10, memory_mb: int = 128):
        self.calls.append((code, stdin))
        return self.result


class FakeMcp:
    def __init__(self, result: ToolResult) -> None:
        self.result = result
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, tool_name, arguments, *, tenant_id, department_id):
        self.calls.append((tool_name, arguments))
        return self.result

    async def list_tools(self, *, tenant_id, department_id):
        return []


def _make_mcp_tool(**overrides) -> Tool:
    defaults = dict(
        id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        department_id=DEPT_ID,
        display_name="rag.search",
        header={},
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        output_schema={
            "type": "object",
            "properties": {"passages": {"type": "array"}},
            "required": ["passages"],
        },
        embedded_python=None,
    )
    defaults.update(overrides)
    return Tool(**defaults)


def _make_sandbox_tool(**overrides) -> Tool:
    defaults = dict(
        id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        department_id=DEPT_ID,
        display_name="double_it",
        header={},
        input_schema={
            "type": "object",
            "properties": {"n": {"type": "number"}},
            "required": ["n"],
        },
        output_schema={
            "type": "object",
            "properties": {"doubled": {"type": "number"}},
            "required": ["doubled"],
        },
        embedded_python="print('{}')",
    )
    defaults.update(overrides)
    return Tool(**defaults)


# ---------------------------------------------------------------------------
# AC2 -- input mismatch -> rejected + audit, downstream ports NEVER called
# ---------------------------------------------------------------------------

def test_input_mismatch_rejects_and_never_calls_downstream_ports() -> None:
    tool = _make_mcp_tool()
    audit = FakeAudit()
    mcp = FakeMcp(ToolResult(tool_name="rag.search", output={"passages": []}))
    sandbox = FakeSandbox(SandboxResult(stdout="", exit_code=0))

    result = invoke_tool(
        object(),
        tool,
        {},  # missing required "query"
        tenant_id=TENANT_ID,
        department_id=DEPT_ID,
        audit=audit,
        sandbox=sandbox,
        mcp_factory=lambda **_: mcp,
    )

    assert result.success is False
    assert "Input validation failed" in result.error
    assert len(audit.entries) == 1
    assert audit.entries[0].type == "tool.rejected"
    assert mcp.calls == []
    assert sandbox.calls == []


# ---------------------------------------------------------------------------
# AC2/AC4 -- valid input -> tool.invoked logged then routed to MCP
# ---------------------------------------------------------------------------

def test_valid_input_logs_invoked_then_routes_to_mcp() -> None:
    tool = _make_mcp_tool()
    audit = FakeAudit()
    mcp = FakeMcp(ToolResult(tool_name="rag.search", output={"passages": ["a"]}))

    result = invoke_tool(
        object(),
        tool,
        {"query": "hello"},
        tenant_id=TENANT_ID,
        department_id=DEPT_ID,
        audit=audit,
        mcp_factory=lambda **_: mcp,
    )

    assert result.success is True
    assert result.output == {"passages": ["a"]}
    assert [e.type for e in audit.entries] == ["tool.invoked"]
    assert mcp.calls == [("rag.search", {"query": "hello"})]


def test_valid_input_routes_to_sandbox_when_embedded_python(monkeypatch) -> None:
    tool = _make_sandbox_tool()
    audit = FakeAudit()
    sandbox = FakeSandbox(
        SandboxResult(stdout='{"doubled": 4}', exit_code=0, output={"doubled": 4})
    )

    result = invoke_tool(
        object(),
        tool,
        {"n": 2},
        tenant_id=TENANT_ID,
        department_id=DEPT_ID,
        audit=audit,
        sandbox=sandbox,
    )

    assert result.success is True
    assert result.output == {"doubled": 4}
    assert sandbox.calls  # sandbox WAS called
    assert [e.type for e in audit.entries] == ["tool.invoked"]


# ---------------------------------------------------------------------------
# AC3 -- output failing output_schema -> rejected + tool.rejected audit
# ---------------------------------------------------------------------------

def test_output_schema_failure_rejects_and_audits() -> None:
    tool = _make_mcp_tool()
    audit = FakeAudit()
    # MCP returns output missing the required "passages" key.
    mcp = FakeMcp(ToolResult(tool_name="rag.search", output={"wrong_key": True}))

    result = invoke_tool(
        object(),
        tool,
        {"query": "hello"},
        tenant_id=TENANT_ID,
        department_id=DEPT_ID,
        audit=audit,
        mcp_factory=lambda **_: mcp,
    )

    assert result.success is False
    assert "Output validation failed" in result.error
    assert [e.type for e in audit.entries] == ["tool.invoked", "tool.rejected"]
    assert audit.entries[-1].output["reason"] == "output_schema_mismatch"


# ---------------------------------------------------------------------------
# AC5 -- sandbox timeout / memory breach -> sandbox_violation
# ---------------------------------------------------------------------------

def test_sandbox_timeout_logs_sandbox_violation() -> None:
    tool = _make_sandbox_tool()
    audit = FakeAudit()
    sandbox = FakeSandbox(SandboxResult(stdout="", exit_code=-9, timed_out=True))

    result = invoke_tool(
        object(),
        tool,
        {"n": 2},
        tenant_id=TENANT_ID,
        department_id=DEPT_ID,
        audit=audit,
        sandbox=sandbox,
    )

    assert result.success is False
    assert [e.type for e in audit.entries] == ["tool.invoked", "tool.sandbox_violation"]
    assert audit.entries[-1].output["timed_out"] is True


def test_sandbox_memory_breach_logs_sandbox_violation() -> None:
    tool = _make_sandbox_tool()
    audit = FakeAudit()
    # Memory breach: not timed_out, but forcibly killed (-9 sentinel).
    sandbox = FakeSandbox(SandboxResult(stdout="", exit_code=-9, timed_out=False))

    result = invoke_tool(
        object(),
        tool,
        {"n": 2},
        tenant_id=TENANT_ID,
        department_id=DEPT_ID,
        audit=audit,
        sandbox=sandbox,
    )

    assert result.success is False
    assert [e.type for e in audit.entries] == ["tool.invoked", "tool.sandbox_violation"]


def test_audit_never_includes_raw_header_secret() -> None:
    """NFR-9 -- audit payloads never carry the Tool's `header` auth secret."""
    tool = _make_mcp_tool(header={"auth": {"token": "super-secret-value"}})
    audit = FakeAudit()
    mcp = FakeMcp(ToolResult(tool_name="rag.search", output={"passages": []}))

    invoke_tool(
        object(),
        tool,
        {"query": "hello"},
        tenant_id=TENANT_ID,
        department_id=DEPT_ID,
        audit=audit,
        mcp_factory=lambda **_: mcp,
    )

    for entry in audit.entries:
        assert "super-secret-value" not in str(entry.input)
        assert "super-secret-value" not in str(entry.output)
