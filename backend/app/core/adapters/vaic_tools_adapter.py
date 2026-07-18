"""VaicToolsAdapter -- real McpClientPort backed by the vaic_tools server.

Routes retrieve/gmail/calendar over MCP Streamable HTTP (/mcp/, Bearer) and
KB ingest/delete over vaic_tools REST (/api/v1/documents). Enforces the
AD-11 client-side department scope before any network call, exactly like
McpClientStub. Names/args/outputs translate via vaic_tools_mapping (pure).

Selected by get_mcp_client when VAIC_TOOLS_ENABLED is true; otherwise the
stub is used. Any transport/upstream error is returned as a failed
ToolResult (success=False) so the caller audits tool.rejected / sets the
KB doc to failed — the adapter never leaks a raw exception except the
AD-11 AuthorizationError, which must propagate.
"""
from __future__ import annotations

import base64
import json
import uuid
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.core.adapters import vaic_tools_mapping as mapping
from app.core.errors import AuthorizationError
from app.core.ids import uuid7
from app.core.ports.mcp_client import McpClientPort, ToolResult

__all__ = ["VaicToolsAdapter"]

_REST_TOOLS = {"rag.ingest", "rag.delete"}
_TIMEOUT_S = 30


class VaicToolsAdapter(McpClientPort):
    def __init__(
        self, *, agent_department_id: uuid.UUID, base_url: str, mcp_url: str, api_key: str
    ) -> None:
        self._agent_department_id = agent_department_id
        self._base_url = base_url.rstrip("/")
        self._mcp_url = mcp_url
        self._api_key = api_key

    def _assert_scope(self, department_id: uuid.UUID) -> None:
        if department_id != self._agent_department_id:
            raise AuthorizationError(
                "VaicToolsAdapter.call_tool: department_id does not match the "
                "calling Agent's Department (AD-11)",
                code="mcp_scope_mismatch",
            )

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> ToolResult:
        self._assert_scope(department_id)
        _ = tenant_id  # scoping only
        try:
            if tool_name in _REST_TOOLS:
                return await self._call_rest(tool_name, arguments)
            return await self._call_mcp(tool_name, arguments)
        except AuthorizationError:
            raise
        except Exception as exc:  # noqa: BLE001 -- surface upstream failures as failed result
            return ToolResult(tool_name=tool_name, output={}, success=False, error=str(exc))

    async def _call_mcp(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        vaic_name = mapping.MCP_TOOL_NAMES[tool_name]
        args = mapping.map_arguments(tool_name, arguments, idempotency_key=str(uuid7()))
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with streamablehttp_client(self._mcp_url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(vaic_name, args)
        if getattr(result, "isError", False):
            text = _first_text(result) or "vaic_tools MCP tool returned an error"
            return ToolResult(tool_name=tool_name, output={}, success=False, error=text)
        raw = _extract_structured(result)
        return ToolResult(
            tool_name=tool_name, output=mapping.map_output(tool_name, raw), success=True
        )

    async def _call_rest(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(base_url=self._base_url, timeout=_TIMEOUT_S) as client:
            if tool_name == "rag.ingest":
                data = base64.b64decode(arguments["data"])
                files = {
                    "file": (
                        arguments["filename"],
                        data,
                        arguments.get("content_type") or "application/octet-stream",
                    )
                }
                resp = await client.post("/api/v1/documents", files=files, headers=headers)
                resp.raise_for_status()
                body = resp.json()
                return ToolResult(
                    tool_name=tool_name,
                    success=True,
                    output={
                        "document_id": body.get("id"),
                        "chunk_count": body.get("chunk_count", 0),
                    },
                )
            # rag.delete
            ext = arguments.get("external_document_id")
            if not ext:
                # Doc was never indexed on vaic (ingest failed) -> nothing to
                # delete upstream. Fail cleanly instead of DELETE .../None.
                return ToolResult(
                    tool_name=tool_name,
                    output={"deleted": False},
                    success=False,
                    error="missing external_document_id; nothing to delete on vaic_tools",
                )
            resp = await client.delete(f"/api/v1/documents/{ext}", headers=headers)
            resp.raise_for_status()
            body = resp.json()
            return ToolResult(
                tool_name=tool_name, success=True, output={"deleted": bool(body.get("deleted"))}
            )

    async def list_tools(
        self, *, tenant_id: uuid.UUID, department_id: uuid.UUID
    ) -> list[str]:
        self._assert_scope(department_id)
        _ = tenant_id
        return ["rag.ingest", "rag.delete", "rag.search", "gmail", "calendar"]


def _first_text(result: Any) -> str:
    content = getattr(result, "content", None) or []
    if content and getattr(content[0], "text", None):
        return content[0].text
    return ""


def _extract_structured(result: Any) -> dict[str, Any]:
    """Pull the tool's dict result from an MCP CallToolResult.

    FastMCP (json_response=True) returns dict tool results as structuredContent.
    Some SDK/server combos wrap a non-dict return under a single "result" key;
    when the dict is exactly {"result": ...} we unwrap it. Falls back to
    JSON-parsing the first text content block.
    """
    sc = getattr(result, "structuredContent", None)
    if isinstance(sc, dict):
        if set(sc.keys()) == {"result"} and isinstance(sc["result"], dict):
            return sc["result"]
        return sc
    text = _first_text(result)
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
    return {}
