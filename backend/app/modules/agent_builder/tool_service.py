"""Tool invocation service — `AgentToolPort` implements `ToolPort` (Story 2.6 T4).

Validates input against `input_schema` (AC2), routes to `SandboxPort`
(embedded Python) or `McpClientPort` (MCP-routed) per AD-1/AD-3, validates
the raw output against `output_schema` (AC3), and audits every outcome
(`tool.invoked` / `tool.rejected` / `tool.sandbox_violation`) through the
injected `AuditPort` (AD-4) — never direct SQL to `audit_trail`.

Scope boundary (Dev Notes): this module builds and unit-tests the
invocation *path* only. The Orchestrator dispatch loop that calls
`ToolPort.invoke` during a live Workflow Run is Epic 3.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.adapters.sandbox import SubprocessSandbox
from app.core.deps import crud_audit_ids, get_mcp_client
from app.core.errors import NotFoundError
from app.core.ids import utcnow_iso_ms
from app.core.ports.audit import AuditEntry, AuditPort
from app.core.ports.mcp_client import McpClientPort
from app.core.ports.sandbox import SandboxPort
from app.core.ports.tool import ToolOutput
from app.modules.agent_builder.models import Tool
from app.modules.agent_builder.schema_validation import validate_instance

__all__ = ["AgentToolPort", "get_tool", "get_tool_by_name", "invoke_tool"]

McpFactory = Callable[..., McpClientPort]


def get_tool(session: Session, *, agent_id: uuid.UUID, tool_id: uuid.UUID) -> Tool:
    """Fetch a single non-deleted Tool scoped to an Agent. RLS hides cross-tenant rows."""
    tool = session.execute(
        select(Tool).where(
            Tool.id == tool_id, Tool.agent_id == agent_id, Tool.is_deleted.is_(False)
        )
    ).scalar_one_or_none()
    if tool is None:
        raise NotFoundError("Tool not found")
    return tool


def get_tool_by_name(session: Session, *, agent_id: uuid.UUID, display_name: str) -> Tool:
    """Fetch a Tool scoped to an Agent by `display_name` (Orchestrator dispatch, Story 3.4)."""
    tool = session.execute(
        select(Tool).where(
            Tool.agent_id == agent_id,
            Tool.display_name == display_name,
            Tool.is_deleted.is_(False),
        )
    ).scalar_one_or_none()
    if tool is None:
        raise NotFoundError(f"Tool '{display_name}' not found for this Agent")
    return tool


def _emit_audit(
    audit: AuditPort,
    tool: Tool,
    entry_type: str,
    *,
    input_payload: dict[str, Any],
    output_payload: dict[str, Any],
    latency_ms: int,
) -> None:
    """Emit one audit entry (AD-4). NEVER includes the raw `header` secret."""
    run_id, step_id = crud_audit_ids(str(tool.id))
    audit.log(
        AuditEntry(
            run_id=run_id,
            step_id=step_id,
            agent_id=str(tool.agent_id),
            ts=utcnow_iso_ms(),
            type=entry_type,
            input=input_payload,
            output=output_payload,
            latency_ms=latency_ms,
            model="",
        )
    )


def _execute(
    tool: Tool,
    arguments: dict[str, Any],
    *,
    tenant_id: uuid.UUID,
    department_id: uuid.UUID,
    sandbox: SandboxPort | None,
    mcp_factory: McpFactory,
) -> tuple[dict[str, Any] | None, Any, int]:
    """Route to sandbox (embedded Python) or MCP; return (raw_output, sandbox_result, latency_ms).

    `sandbox_result` is the raw `SandboxResult` (None for MCP-routed calls) so
    the caller can inspect `timed_out`/`exit_code` for AC5 without re-running.
    """
    start = time.monotonic()
    if tool.embedded_python:
        sandbox_port = sandbox or SubprocessSandbox()
        result = sandbox_port.run(tool.embedded_python, stdin=_to_json(arguments))
        latency_ms = int((time.monotonic() - start) * 1000)
        if result.timed_out or result.exit_code < 0:
            return None, result, latency_ms
        return result.output, result, latency_ms

    mcp = mcp_factory(agent_department_id=department_id)
    mcp_result = _call_mcp(mcp, tool.display_name, arguments, tenant_id, department_id)
    latency_ms = int((time.monotonic() - start) * 1000)
    return mcp_result.output, None, latency_ms


def invoke_tool(
    session: Session,
    tool: Tool,
    arguments: dict[str, Any],
    *,
    tenant_id: uuid.UUID,
    department_id: uuid.UUID,
    audit: AuditPort | None = None,
    sandbox: SandboxPort | None = None,
    mcp_factory: McpFactory = get_mcp_client,
) -> ToolOutput:
    """Validate -> route (sandbox|MCP) -> validate output -> audit (AC2-AC5).

    Shared by `AgentToolPort.invoke` (Orchestrator-facing, Epic 3 consumer)
    and the Test-Tool route (AC7) so both exercise the IDENTICAL path.
    """
    _ = session  # reserved for future Tool-scoped lookups; not needed here
    audit_port = audit or PostgresAuditSink()
    tool_name = tool.display_name

    # -- AC2: input validation -----------------------------------------
    input_errors = validate_instance(tool.input_schema, arguments)
    if input_errors:
        _emit_audit(
            audit_port,
            tool,
            "tool.rejected",
            input_payload={"tool_id": str(tool.id), "arguments": arguments},
            output_payload={"reason": "input_schema_mismatch", "errors": input_errors},
            latency_ms=0,
        )
        return ToolOutput(
            tool_name=tool_name,
            output={},
            success=False,
            error=f"Input validation failed: {'; '.join(input_errors)}",
        )

    _emit_audit(
        audit_port,
        tool,
        "tool.invoked",
        input_payload={"tool_id": str(tool.id), "arguments": arguments},
        output_payload={},
        latency_ms=0,
    )

    # -- AC4: route to sandbox (embedded Python) or MCP -----------------
    raw_output, sandbox_result, latency_ms = _execute(
        tool,
        arguments,
        tenant_id=tenant_id,
        department_id=department_id,
        sandbox=sandbox,
        mcp_factory=mcp_factory,
    )

    # -- AC5: timeout / memory breach -> sandbox_violation --------------
    if sandbox_result is not None and raw_output is None:
        _emit_audit(
            audit_port,
            tool,
            "tool.sandbox_violation",
            input_payload={"tool_id": str(tool.id)},
            output_payload={
                "timed_out": sandbox_result.timed_out,
                "exit_code": sandbox_result.exit_code,
                "stderr": sandbox_result.stderr[:2000],
            },
            latency_ms=latency_ms,
        )
        return ToolOutput(
            tool_name=tool_name,
            output={},
            success=False,
            error="Sandbox execution terminated (timeout or memory breach)",
            latency_ms=latency_ms,
        )

    # -- AC3: output validation -------------------------------------------
    output_errors = validate_instance(tool.output_schema, raw_output)
    if output_errors:
        _emit_audit(
            audit_port,
            tool,
            "tool.rejected",
            input_payload={"tool_id": str(tool.id)},
            output_payload={"reason": "output_schema_mismatch", "errors": output_errors},
            latency_ms=latency_ms,
        )
        return ToolOutput(
            tool_name=tool_name,
            output={},
            success=False,
            error=f"Output validation failed: {'; '.join(output_errors)}",
            latency_ms=latency_ms,
        )

    return ToolOutput(
        tool_name=tool_name, output=raw_output, success=True, latency_ms=latency_ms
    )


def _call_mcp(
    mcp: McpClientPort,
    tool_name: str,
    arguments: dict[str, Any],
    tenant_id: uuid.UUID,
    department_id: uuid.UUID,
):  # noqa: ANN202 -- returns McpClientPort's ToolResult
    """Run the async `McpClientPort.call_tool` synchronously (AD-3, AD-11)."""
    import asyncio

    return asyncio.run(
        mcp.call_tool(
            tool_name, arguments, tenant_id=tenant_id, department_id=department_id
        )
    )


def _to_json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value)


class AgentToolPort:
    """`ToolPort` implementation, scoped to one Agent's registered Tools.

    Resolves a Tool by its `display_name` within the bound Agent, then
    delegates to `invoke_tool` for the validate/route/validate/audit path.
    """

    def __init__(
        self,
        session: Session,
        *,
        agent_id: uuid.UUID,
        audit: AuditPort | None = None,
        sandbox: SandboxPort | None = None,
        mcp_factory: McpFactory = get_mcp_client,
    ) -> None:
        self._session = session
        self._agent_id = agent_id
        self._audit = audit
        self._sandbox = sandbox
        self._mcp_factory = mcp_factory

    async def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> ToolOutput:
        tool = self._session.execute(
            select(Tool).where(
                Tool.agent_id == self._agent_id,
                Tool.display_name == name,
                Tool.is_deleted.is_(False),
            )
        ).scalar_one_or_none()
        if tool is None:
            raise NotFoundError(f"Tool '{name}' not found for this Agent")

        return invoke_tool(
            self._session,
            tool,
            arguments,
            tenant_id=tenant_id,
            department_id=department_id,
            audit=self._audit,
            sandbox=self._sandbox,
            mcp_factory=self._mcp_factory,
        )
