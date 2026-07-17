"""Unit tests for hexagonal port interfaces (Protocols).

Covers ACs:
- Every port is a typing.Protocol (not a concrete class)
- LlmPort exposes complete, stream, embed with correct signatures
- AuditPort.log signature matches PRD FR-21 AuditEntry field shape
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


def test_audit_port_has_log_method() -> None:
    """AuditPort declares `log`."""
    from app.core.ports.audit import AuditPort

    assert hasattr(AuditPort, "log")
    assert callable(AuditPort.log)


def test_audit_entry_has_fr21_fields() -> None:
    """AuditEntry has the exact field names from PRD FR-21."""
    from app.core.ports.audit import AuditEntry

    fields = AuditEntry.model_fields
    expected = {"run_id", "step_id", "agent_id", "ts", "type", "input", "output",
                "latency_ms", "model"}
    assert set(fields.keys()) == expected


def test_audit_port_structural_compliance() -> None:
    """A class with log(entry) satisfies AuditPort."""
    from app.core.ports.audit import AuditPort

    class FakeAudit:
        def log(self, entry) -> None: ...  # noqa: ANN001

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
        assert "tenant_id" in params, (
            f"McpClientPort.{name} must accept tenant_id (AD-11)"
        )
        assert "department_id" in params, (
            f"McpClientPort.{name} must accept department_id (AD-11)"
        )


def test_mcp_client_port_structural_compliance() -> None:
    """A class implementing all McpClientPort methods satisfies the Protocol."""
    from app.core.ports.mcp_client import McpClientPort

    class FakeMcp:
        async def call_tool(
            self, tool_name, arguments, *, tenant_id, department_id,  # noqa: ANN001
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


# -- AgentProviderPort (Story 2.5, deferred from 1.4) ------------------------

def test_agent_provider_port_is_protocol() -> None:
    """AgentProviderPort is a Protocol."""
    from app.core.ports.agent_provider import AgentProviderPort

    assert _is_protocol(AgentProviderPort)


def test_agent_provider_port_has_retrieve_method() -> None:
    """AgentProviderPort declares `retrieve`."""
    from app.core.ports.agent_provider import AgentProviderPort

    assert hasattr(AgentProviderPort, "retrieve")
    assert callable(AgentProviderPort.retrieve)


def test_agent_provider_port_retrieve_requires_tenant_and_department() -> None:
    """`retrieve` carries the AD-11 keyword-only tenant_id + department_id."""
    from app.core.ports.agent_provider import AgentProviderPort

    sig = inspect.signature(AgentProviderPort.retrieve)
    params = set(sig.parameters.keys())
    assert "tenant_id" in params
    assert "department_id" in params


def test_agent_provider_port_structural_compliance() -> None:
    """A fake implementing `retrieve()` satisfies `isinstance(fake, AgentProviderPort)`."""
    from app.core.ports.agent_provider import AgentProviderPort

    class FakeAgentProvider:
        async def retrieve(  # noqa: ANN001
            self, agent_id, query, *, tenant_id, department_id, top_k=5
        ): ...

    assert isinstance(FakeAgentProvider(), AgentProviderPort)


def test_retrieval_passage_model_has_exact_fields() -> None:
    """RetrievalPassage exposes exactly {passage, document_name, chunk_reference, score} (AC3)."""
    from app.core.ports.agent_provider import RetrievalPassage

    fields = RetrievalPassage.model_fields
    assert set(fields.keys()) == {"passage", "document_name", "chunk_reference", "score"}


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


# -- SubprocessSandbox / AgentToolPort structural compliance (Story 2.6) ----

def test_subprocess_sandbox_satisfies_sandbox_port() -> None:
    """`SubprocessSandbox` structurally satisfies `SandboxPort` (AC4/AC5)."""
    from app.core.adapters.sandbox import SubprocessSandbox
    from app.core.ports.sandbox import SandboxPort

    assert isinstance(SubprocessSandbox(), SandboxPort)


def test_agent_tool_port_satisfies_tool_port() -> None:
    """`AgentToolPort` structurally satisfies `ToolPort` (AC2-AC5)."""
    import uuid

    from app.core.ports.tool import ToolPort
    from app.modules.agent_builder.tool_service import AgentToolPort

    fake_session = object()
    port = AgentToolPort(fake_session, agent_id=uuid.uuid4())  # type: ignore[arg-type]
    assert isinstance(port, ToolPort)
