"""McpClientStub -- stub implementation of `McpClientPort` (AD-3, AD-11).

Story 2.4 T3: VAIC is an MCP **client** only (AD-3). The real MCP server
(`rag.ingest`, `rag.delete`, `rag.search`, ...) is built by the parallel
team. Until it lands, this stub returns a successful, fabricated result for
every ``rag.*`` tool call so the KB upload/delete slice is fully wired and
testable end-to-end.

AD-11 (client-side scope enforcement): every ``call_tool`` MUST receive
``tenant_id`` + ``department_id`` scoped to the calling Agent's own
Department. This stub raises ``AuthorizationError`` *before* any (simulated)
network call when the caller-supplied ``department_id`` does not match the
Agent's Department -- the same pre-network-raise contract Story 2.5 relies
on. The check lives HERE (the implementation), never only in the service.
"""

from __future__ import annotations

import uuid

from app.core.errors import AuthorizationError
from app.core.ids import uuid7
from app.core.ports.mcp_client import McpClientPort, ToolResult

__all__ = ["McpClientStub"]


class McpClientStub(McpClientPort):
    """Fabricates successful `rag.*` tool results for local dev + tests.

    ``agent_department_id`` is the Department the calling Agent actually
    belongs to (loaded by the caller). Every `call_tool` verifies the
    passed `department_id` matches it before "sending" the request.
    """

    def __init__(self, *, agent_department_id: uuid.UUID) -> None:
        self._agent_department_id = agent_department_id

    def _assert_scope(self, department_id: uuid.UUID) -> None:
        """AD-11: raise before the network on a department mismatch."""
        if department_id != self._agent_department_id:
            raise AuthorizationError(
                "McpClientStub.call_tool: department_id does not match the "
                "calling Agent's Department (AD-11)",
                code="mcp_scope_mismatch",
            )

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> ToolResult:
        """Return a fabricated success result for `rag.ingest` / `rag.delete`."""
        self._assert_scope(department_id)
        _ = tenant_id  # scoping only; stub does not persist anything.

        if tool_name == "rag.ingest":
            return ToolResult(
                tool_name=tool_name,
                output={
                    "document_id": str(uuid7()),
                    "chunk_count": max(1, len(arguments.get("data", b"")) // 1000 or 1),
                },
                success=True,
            )
        if tool_name == "rag.delete":
            return ToolResult(tool_name=tool_name, output={"deleted": True}, success=True)
        if tool_name == "rag.search":
            # AC8 placeholder -- runtime retrieval is Story 2.5; the stub
            # returns an empty passage set so the client path is exercised
            # without implementing the real tool here.
            return ToolResult(tool_name=tool_name, output={"passages": []}, success=True)
        if tool_name == "gmail":
            return ToolResult(
                tool_name=tool_name,
                output={"message_id": "stub-msg", "status": "sent"},
                success=True,
            )
        if tool_name == "calendar":
            return ToolResult(
                tool_name=tool_name,
                output={"event_id": "stub-evt", "status": "created"},
                success=True,
            )

        return ToolResult(
            tool_name=tool_name,
            output={},
            success=False,
            error=f"Unknown tool: {tool_name}",
        )

    async def list_tools(
        self,
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> list[str]:
        """Return the stubbed tool names available for this scope."""
        self._assert_scope(department_id)
        _ = tenant_id
        return ["rag.ingest", "rag.delete", "rag.search"]
