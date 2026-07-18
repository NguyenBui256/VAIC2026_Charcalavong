"""Unit tests for hexagonal port interfaces (Protocols).

Covers ACs:
- Every port is a typing.Protocol (not a concrete class)
- LlmPort exposes complete, stream, embed with correct signatures
- AuditPort exposes structured session/span/event lifecycle methods
- McpClientPort REQUIRES tenant_id + department_id on every method
- ToolPort, DocIntakePort, SandboxPort are Protocols with correct methods
"""

from __future__ import annotations

import inspect
import typing

# -- Protocol check helper ---------------------------------------------------


def _is_protocol(cls: type) -> bool:
    """Return True if cls is a typing.Protocol."""
    return typing.get_origin(cls) is None and getattr(cls, "_is_protocol", False)


# -- LlmPort -----------------------------------------------------------------


def test_llm_port_is_protocol() -> None:
    """LlmPort is a Protocol, not a concrete class."""
    from app.core.ports.llm import LlmPort

    assert _is_protocol(LlmPort)


def test_llm_port_has_complete_method() -> None:
    """LlmPort declares a `complete` method."""
    from app.core.ports.llm import LlmPort

    assert hasattr(LlmPort, "complete")
    assert callable(LlmPort.complete)


def test_llm_port_has_stream_method() -> None:
    """LlmPort declares a `stream` method."""
    from app.core.ports.llm import LlmPort

    assert hasattr(LlmPort, "stream")
    assert callable(LlmPort.stream)


def test_llm_port_has_embed_method() -> None:
    """LlmPort declares an `embed` method."""
    from app.core.ports.llm import LlmPort

    assert hasattr(LlmPort, "embed")
    assert callable(LlmPort.embed)


def test_llm_port_structural_compliance() -> None:
    """A class implementing all three methods satisfies LlmPort structurally."""
    from app.core.ports.llm import LlmPort

    class FakeLlm:
        def complete(self, messages, model, parameters): ...  # noqa: ANN001
        async def stream(self, messages, model, parameters): ...  # noqa: ANN001
        def embed(self, texts, model): ...  # noqa: ANN001

    assert isinstance(FakeLlm(), LlmPort)


# -- AuditPort ---------------------------------------------------------------


def test_audit_port_is_protocol() -> None:
    """AuditPort is a Protocol."""
    from app.core.ports.audit import AuditPort

    assert _is_protocol(AuditPort)


def test_audit_port_has_v2_lifecycle_methods() -> None:
    """AuditPort exposes session/span/event lifecycle methods."""
    from app.core.ports.audit import AuditPort

    expected = {"start_session", "start_span", "emit_event", "end_span", "end_session", "span"}
    assert all(callable(getattr(AuditPort, name)) for name in expected)


def test_execution_context_has_correlation_fields() -> None:
    from app.core.ports.audit import ExecutionContext

    expected = {
        "tenant_id",
        "session_id",
        "run_id",
        "trace_id",
        "span_id",
        "parent_span_id",
        "task_id",
        "agent_id",
        "department_id",
        "attempt_no",
        "correlation_id",
    }
    assert set(ExecutionContext.model_fields) == expected


def test_audit_port_structural_compliance() -> None:
    """A class with log(entry) satisfies AuditPort."""
    from app.core.ports.audit import AuditPort

    class FakeAudit:
        def start_session(self, value): ...  # noqa: ANN001
        def start_span(self, value): ...  # noqa: ANN001
        def emit_event(self, value): ...  # noqa: ANN001
        def end_span(self, value): ...  # noqa: ANN001
        def end_session(self, value): ...  # noqa: ANN001
        def span(self, value): ...  # noqa: ANN001

    assert isinstance(FakeAudit(), AuditPort)


# -- McpClientPort -----------------------------------------------------------


def test_mcp_client_port_is_protocol() -> None:
    """McpClientPort is a Protocol."""
    from app.core.ports.mcp_client import McpClientPort

    assert _is_protocol(McpClientPort)


def test_mcp_client_port_has_call_tool() -> None:
    """McpClientPort declares `call_tool`."""
    from app.core.ports.mcp_client import McpClientPort

    assert hasattr(McpClientPort, "call_tool")


def test_mcp_client_port_call_tool_requires_tenant_and_department() -> None:
    """Every McpClientPort method signature includes tenant_id + department_id (AD-11)."""
    from app.core.ports.mcp_client import McpClientPort

    for name in dir(McpClientPort):
        if name.startswith("_"):
            continue
        attr = getattr(McpClientPort, name, None)
        if not callable(attr):
            continue
        sig = inspect.signature(attr)
        params = set(sig.parameters.keys())
        assert "tenant_id" in params, f"McpClientPort.{name} must accept tenant_id (AD-11)"
        assert "department_id" in params, f"McpClientPort.{name} must accept department_id (AD-11)"


def test_mcp_client_port_structural_compliance() -> None:
    """A class implementing all McpClientPort methods satisfies the Protocol."""
    from app.core.ports.mcp_client import McpClientPort

    class FakeMcp:
        async def call_tool(
            self,
            tool_name,
            arguments,
            *,
            tenant_id,
            department_id,  # noqa: ANN001
        ): ...
        async def list_tools(self, *, tenant_id, department_id): ...  # noqa: ANN001

    assert isinstance(FakeMcp(), McpClientPort)


# -- ToolPort ----------------------------------------------------------------


def test_tool_port_is_protocol() -> None:
    """ToolPort is a Protocol."""
    from app.core.ports.tool import ToolPort

    assert _is_protocol(ToolPort)


def test_tool_port_has_invoke() -> None:
    """ToolPort declares `invoke`."""
    from app.core.ports.tool import ToolPort

    assert hasattr(ToolPort, "invoke")


def test_tool_port_structural_compliance() -> None:
    """A class with invoke() satisfies ToolPort."""
    from app.core.ports.tool import ToolPort

    class FakeTool:
        async def invoke(self, name, arguments, *, tenant_id, department_id): ...  # noqa: ANN001

    assert isinstance(FakeTool(), ToolPort)


# -- DocIntakePort -----------------------------------------------------------


def test_doc_intake_port_is_protocol() -> None:
    """DocIntakePort is a Protocol."""
    from app.core.ports.doc_intake import DocIntakePort

    assert _is_protocol(DocIntakePort)


def test_doc_intake_port_has_ingest() -> None:
    """DocIntakePort declares `ingest`."""
    from app.core.ports.doc_intake import DocIntakePort

    assert hasattr(DocIntakePort, "ingest")


def test_doc_intake_port_structural_compliance() -> None:
    """A class implementing all DocIntakePort methods satisfies the Protocol."""
    from app.core.ports.doc_intake import DocIntakePort

    class FakeDocIntake:
        async def ingest(self, agent_id, document, *, tenant_id, department_id): ...  # noqa: ANN001
        async def retrieve(self, agent_id, query, *, tenant_id, department_id): ...  # noqa: ANN001

    assert isinstance(FakeDocIntake(), DocIntakePort)


# -- SandboxPort -------------------------------------------------------------


def test_sandbox_port_is_protocol() -> None:
    """SandboxPort is a Protocol."""
    from app.core.ports.sandbox import SandboxPort

    assert _is_protocol(SandboxPort)


def test_sandbox_port_has_run() -> None:
    """SandboxPort declares `run`."""
    from app.core.ports.sandbox import SandboxPort

    assert hasattr(SandboxPort, "run")


def test_sandbox_port_structural_compliance() -> None:
    """A class with run() satisfies SandboxPort."""
    from app.core.ports.sandbox import SandboxPort

    class FakeSandbox:
        def run(self, code, stdin, *, timeout_s=10, memory_mb=128): ...  # noqa: ANN001

    assert isinstance(FakeSandbox(), SandboxPort)


# -- Protocol models ---------------------------------------------------------


def test_llm_message_model_exists() -> None:
    """LlmPort's Message model has role and content fields."""
    from app.core.ports.llm import Message

    fields = Message.model_fields
    assert "role" in fields
    assert "content" in fields


def test_llm_completion_result_model_exists() -> None:
    """LlmPort's CompletionResult model has the expected fields."""
    from app.core.ports.llm import CompletionResult

    fields = CompletionResult.model_fields
    assert "content" in fields
    assert "model" in fields
    assert "latency_ms" in fields
