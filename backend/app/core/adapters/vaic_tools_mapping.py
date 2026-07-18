"""Pure translation between VAIC platform tool contracts and vaic_tools.

No I/O. Maps the platform's internal call_tool names/args/outputs to the
vaic_tools MCP tool signatures (and back). Kept separate from transport
(vaic_tools_adapter.py) so the mapping is unit-testable without a network.
"""
from __future__ import annotations

from typing import Any

__all__ = ["MCP_TOOL_NAMES", "map_arguments", "map_output"]

# platform call_tool name -> vaic_tools MCP tool name
MCP_TOOL_NAMES: dict[str, str] = {
    "rag.search": "retrieve_knowledge",
    "gmail": "send_gmail_email",
    "calendar": "create_calendar_event",
}


def map_arguments(
    platform_tool: str, arguments: dict[str, Any], *, idempotency_key: str
) -> dict[str, Any]:
    """Translate platform tool args -> vaic_tools MCP tool args.

    gmail/calendar require `idempotency_key` (min 8 chars) — injected here.
    """
    if platform_tool == "rag.search":
        args: dict[str, Any] = {"query": arguments["query"]}
        if arguments.get("top_k") is not None:
            args["top_k"] = arguments["top_k"]
        if arguments.get("document_ids"):
            args["document_ids"] = arguments["document_ids"]
        return args
    if platform_tool == "gmail":
        to = arguments["to"]
        return {
            "idempotency_key": idempotency_key,
            "to": [to] if isinstance(to, str) else list(to),
            "subject": arguments["subject"],
            "text_body": arguments.get("body") or arguments.get("text_body"),
        }
    if platform_tool == "calendar":
        out: dict[str, Any] = {
            "idempotency_key": idempotency_key,
            "summary": arguments.get("title") or arguments.get("summary"),
            "start": arguments["start"],
            "end": arguments["end"],
        }
        if arguments.get("attendees"):
            out["attendees"] = arguments["attendees"]
        return out
    raise ValueError(f"Unsupported MCP tool: {platform_tool}")


def map_output(platform_tool: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Translate vaic_tools tool output -> the platform's expected output shape."""
    if platform_tool == "rag.search":
        return {
            "passages": [
                {
                    "passage": item.get("text", ""),
                    "document_name": (item.get("source") or {}).get("filename", ""),
                    "chunk_reference": _chunk_ref(item.get("source") or {}),
                    "score": float(item.get("score", 0.0)),
                }
                for item in raw.get("results", [])
            ]
        }
    if platform_tool == "gmail":
        return {"message_id": raw.get("message_id", ""), "status": raw.get("status", "")}
    if platform_tool == "calendar":
        return {"event_id": raw.get("event_id", ""), "status": raw.get("status", "")}
    raise ValueError(f"Unsupported MCP tool: {platform_tool}")


def _chunk_ref(source: dict[str, Any]) -> str:
    section = source.get("section") or ""
    chunk_index = source.get("chunk_index")
    return f"{section}#{chunk_index}" if chunk_index is not None else section
