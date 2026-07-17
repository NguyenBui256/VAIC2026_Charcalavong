"""McpClientPort -- hexagonal port for the MCP client (AD-3, AD-11).

VAIC is an MCP **client**. Tools owned by the parallel-team MCP server
(``rag.search``, ``gmail.send``, ``calendar.write``, etc.) are invoked through
this port.

Per AD-11: Every call MUST include ``tenant_id`` and ``department_id``.
The implementation enforces client-side that these match the calling Agent's
department. A mismatch raises before it hits the network. VAIC never sends an
unscoped MCP call.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

__all__ = ["McpClientPort", "ToolResult"]


class ToolResult(BaseModel):
    """Result of an MCP tool invocation."""

    tool_name: str
    output: dict[str, Any]
    success: bool = True
    error: str = ""


@runtime_checkable
class McpClientPort(Protocol):
    """Hexagonal port for MCP tool invocations.

    Implementation: ``core/adapters/mcp_client.py`` (future epic).

    AD-11: Every method MUST accept ``tenant_id`` and ``department_id``.
    The implementation MUST verify these match the calling Agent's context
    before sending the request to the MCP server.
    """

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> ToolResult:
        """Invoke a tool on the MCP server.

        Args:
            tool_name: the tool to call (e.g. ``rag.search``).
            arguments: tool-specific arguments.
            tenant_id: the calling tenant (AD-11, required).
            department_id: the calling department (AD-11, required).

        Raises:
            AuthorizationError: if tenant_id/department_id mismatch the context.
            UpstreamError: if the MCP server is unreachable or returns an error.
        """
        ...

    async def list_tools(
        self,
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> list[str]:
        """List available tools for the given tenant + department scope."""
        ...
