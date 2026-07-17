"""ToolPort -- unified interface for MCP tools and embedded Python tools.

Per structural-seed.md: ``ToolPort (MCP + embedded-Python unified)``.
An Agent's configured Tools may be either:
- MCP tools -- invoked through ``McpClientPort`` (AD-3).
- Embedded Python tools -- executed in a sandbox (``SandboxPort``).

This port abstracts over both so Agent code does not care which kind it calls.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

__all__ = ["ToolPort", "ToolInvocation", "ToolOutput"]


class ToolInvocation(BaseModel):
    """A request to invoke a tool."""

    tool_name: str
    arguments: dict[str, Any]
    tenant_id: uuid.UUID
    department_id: uuid.UUID


class ToolOutput(BaseModel):
    """The result of a tool invocation."""

    tool_name: str
    output: dict[str, Any]
    success: bool = True
    error: str = ""
    latency_ms: int = 0


@runtime_checkable
class ToolPort(Protocol):
    """Unified tool interface for MCP and embedded Python tools.

    The implementation routes to ``McpClientPort`` or ``SandboxPort`` based on
    the Tool's configuration.
    """

    async def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> ToolOutput:
        """Invoke a tool by name with the given arguments.

        Args:
            name: the registered tool name.
            arguments: tool-specific input.
            tenant_id: calling tenant (required for MCP per AD-11).
            department_id: calling department (required for MCP per AD-11).

        Returns:
            ToolOutput with the result or error.
        """
        ...
