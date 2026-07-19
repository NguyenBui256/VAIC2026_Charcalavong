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

_REST_TOOLS = {"rag.ingest", "rag.delete", "rag.progress"}
# Must be >= kb_service.INGEST_TIMEOUT_S so the httpx client doesn't abort a
# large-PDF ingest before the backend's own wait_for ceiling. Ingest now runs
# in a background task, so a long client timeout doesn't block any request.
_TIMEOUT_S = 300


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
                # external_ref = caller document id, lets vaic_tools key live
                # ingest progress back to us (GET /api/v1/documents/progress).
                form = {"external_ref": str(arguments["document_id"])} if arguments.get("document_id") else None
                resp = await client.post(
                    "/api/v1/documents", files=files, data=form, headers=headers
                )
                if resp.status_code >= 400:
                    # Surface the upstream envelope message (e.g. "No indexable
                    # text...", "This content is already indexed...") instead of
                    # the raw httpx "Client error '409 Conflict' for url ..."
                    return ToolResult(
                        tool_name=tool_name, output={}, success=False,
                        error=_rest_error(resp),
                    )
                body = resp.json()
                return ToolResult(
                    tool_name=tool_name,
                    success=True,
                    output={
                        "document_id": body.get("id"),
                        "chunk_count": body.get("chunk_count", 0),
                    },
                )
            if tool_name == "rag.progress":
                resp = await client.get(
                    "/api/v1/documents/progress",
                    params={"ref": str(arguments.get("external_ref"))},
                    headers=headers,
                )
                if resp.status_code >= 400:
                    return ToolResult(
                        tool_name=tool_name, output={}, success=False, error=_rest_error(resp)
                    )
                return ToolResult(tool_name=tool_name, output=resp.json(), success=True)
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
            if resp.status_code >= 400:
                return ToolResult(
                    tool_name=tool_name, output={"deleted": False}, success=False,
                    error=_rest_error(resp),
                )
            body = resp.json()
            return ToolResult(
                tool_name=tool_name, success=True, output={"deleted": bool(body.get("deleted"))}
            )

    async def list_tools(
        self, *, tenant_id: uuid.UUID, department_id: uuid.UUID
    ) -> list[str]:
        self._assert_scope(department_id)
        _ = tenant_id
        return ["rag.ingest", "rag.delete", "rag.progress", "rag.search", "gmail", "calendar"]


def _rest_error(resp: httpx.Response) -> str:
    """Extract a human-readable message from a vaic_tools REST error response.

    vaic_tools returns {"error": {"code", "message", ...}} on failure; fall
    back to a plain HTTP-status string when the body isn't that envelope.
    """
    try:
        body = resp.json()
        err = body.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
    except Exception:  # noqa: BLE001 -- non-JSON / unexpected body
        pass
    return f"vaic_tools returned HTTP {resp.status_code}"


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
