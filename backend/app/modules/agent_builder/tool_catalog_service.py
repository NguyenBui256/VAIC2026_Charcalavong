"""Tenant-wide Tool catalog service (Sub-project A / Shared Pool).

Built-in tools (`rag`/`gmail`/`calendar`, `kind="builtin"`) are seeded per
tenant and are NEVER user-editable via the API. `kind="integration"` tools
wrap a tenant `ApiIntegration` (Sub-project A shared pool) and are fully
CRUD-managed by `builder`-role principals (`require_builder`, Task 1).
Agents reference catalog tools via `agent_tools`; attach/detach of that
grant keeps the existing builder-or-owner mutation guard (`_authorize_mutation`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, ValidationError
from app.core.perms import require_builder
from app.core.tenant_context import tenant_context
from app.modules.agent_builder.models import AgentTool, ApiIntegration, Tool
from app.modules.agent_builder.service import Principal, _authorize_mutation, get_agent

__all__ = [
    "DEFAULT_TOOL_SPECS",
    "list_catalog_tools",
    "get_catalog_tool",
    "serialize_tool",
    "list_agent_tool_refs",
    "attach_agent_tool",
    "detach_agent_tool",
    "seed_default_tools",
    "create_catalog_tool",
    "update_catalog_tool",
    "delete_catalog_tool",
]

# The built-in catalog. `params_schema` is the LLM call interface (spec D5).
DEFAULT_TOOL_SPECS: tuple[dict[str, Any], ...] = (
    {
        "tool_type": "rag",
        "display_name": "Knowledge Base Search (RAG)",
        "description": (
            "Search the agent's granted Knowledge Base documents for passages "
            "relevant to a query. Only documents granted to this agent are searched."
        ),
        "params_schema": {
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}},
        },
        "output_schema": {"type": "object"},
        "config": {},
    },
    {
        "tool_type": "gmail",
        "display_name": "Send Gmail",
        "description": (
            "Send an email on the user's behalf. Provide the recipient address, "
            "subject line, and message body."
        ),
        "params_schema": {
            "type": "object",
            "required": ["to", "subject", "body"],
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}, "status": {"type": "string"}},
        },
        "config": {},
    },
    {
        "tool_type": "calendar",
        "display_name": "Create Calendar Event",
        "description": (
            "Create a calendar event. Provide a title, start and end time "
            "(ISO 8601), and optional attendees."
        ),
        "params_schema": {
            "type": "object",
            "required": ["title", "start", "end"],
            "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "description": "ISO 8601 datetime"},
                "end": {"type": "string", "description": "ISO 8601 datetime"},
                "attendees": {"type": "array", "items": {"type": "string"}},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {"event_id": {"type": "string"}, "status": {"type": "string"}},
        },
        "config": {},
    },
)


def list_catalog_tools(session: Session) -> list[Tool]:
    """All non-deleted catalog tools in the tenant (RLS-scoped)."""
    return list(
        session.execute(
            select(Tool).where(Tool.is_deleted.is_(False)).order_by(Tool.display_name)
        ).scalars().all()
    )


def get_catalog_tool(session: Session, tool_id: uuid.UUID) -> Tool:
    tool = session.execute(
        select(Tool).where(Tool.id == tool_id, Tool.is_deleted.is_(False))
    ).scalar_one_or_none()
    if tool is None:
        raise NotFoundError("Tool not found")
    return tool


def serialize_tool(tool: Tool) -> dict:
    """Response shape — never exposes `credential_ref`."""
    return {
        "id": str(tool.id),
        "tool_type": tool.tool_type,
        "display_name": tool.display_name,
        "description": tool.description,
        "params_schema": tool.params_schema,
        "output_schema": tool.output_schema,
        "config": tool.config,
        "kind": tool.kind,
        "integration_id": str(tool.integration_id) if tool.integration_id else None,
        "created_at": tool.created_at.isoformat(timespec="milliseconds"),
        "updated_at": tool.updated_at.isoformat(timespec="milliseconds"),
    }


def list_agent_tool_refs(session: Session, *, agent_id: uuid.UUID) -> list[Tool]:
    """Catalog tools this agent references (via `agent_tools`)."""
    return list(
        session.execute(
            select(Tool)
            .join(AgentTool, AgentTool.tool_id == Tool.id)
            .where(AgentTool.agent_id == agent_id, Tool.is_deleted.is_(False))
            .order_by(Tool.display_name)
        ).scalars().all()
    )


def attach_agent_tool(
    session: Session, *, agent_id: uuid.UUID, tool_id: uuid.UUID, principal: Principal
) -> None:
    """Add an agent→tool reference (idempotent). Guarded like an agent mutation."""
    agent = get_agent(session, agent_id)
    _authorize_mutation(agent, principal)
    tool = get_catalog_tool(session, tool_id)  # 404 if not in tenant
    existing = session.get(AgentTool, {"agent_id": agent_id, "tool_id": tool.id})
    if existing is not None:
        return
    session.add(
        AgentTool(agent_id=agent_id, tool_id=tool.id, tenant_id=tenant_context.get())
    )
    session.commit()


def detach_agent_tool(
    session: Session, *, agent_id: uuid.UUID, tool_id: uuid.UUID, principal: Principal
) -> None:
    """Remove an agent→tool reference (idempotent)."""
    agent = get_agent(session, agent_id)
    _authorize_mutation(agent, principal)
    row = session.get(AgentTool, {"agent_id": agent_id, "tool_id": tool_id})
    if row is not None:
        session.delete(row)
        session.commit()


def _get_active_integration(session: Session, integration_id: uuid.UUID) -> ApiIntegration:
    """Verify the integration exists (tenant-scoped via RLS) and is not deleted."""
    integ = session.get(ApiIntegration, integration_id)
    if integ is None or integ.is_deleted:
        raise NotFoundError("Integration not found")
    return integ


def create_catalog_tool(
    session: Session,
    *,
    principal: Principal,
    display_name: str,
    description: str,
    params_schema: dict[str, Any],
    output_schema: dict[str, Any],
    integration_id: uuid.UUID,
) -> Tool:
    """Create a `kind="integration"` catalog tool. Builder role required."""
    from app.core.ids import uuid7

    require_builder(principal)
    _get_active_integration(session, integration_id)

    tool = Tool(
        id=uuid7(),
        tenant_id=tenant_context.get(),
        owner_id=principal.user_id,
        tool_type="integration",
        kind="integration",
        display_name=display_name,
        description=description,
        params_schema=params_schema,
        output_schema=output_schema,
        config={},
        integration_id=integration_id,
    )
    session.add(tool)
    session.commit()
    session.refresh(tool)
    return tool


def update_catalog_tool(
    session: Session,
    tool_id: uuid.UUID,
    *,
    principal: Principal,
    **changes: object,
) -> Tool:
    """Update a `kind="integration"` catalog tool. Builder role required.

    Built-in tools (`kind="builtin"`) can never be mutated through the API.
    """
    require_builder(principal)
    tool = get_catalog_tool(session, tool_id)
    if tool.kind == "builtin":
        raise ValidationError("Built-in tools cannot be modified", code="builtin_tool_immutable")

    if (display_name := changes.get("display_name")) is not None:
        tool.display_name = display_name  # type: ignore[assignment]
    if (description := changes.get("description")) is not None:
        tool.description = description  # type: ignore[assignment]
    if "params_schema" in changes and changes["params_schema"] is not None:
        tool.params_schema = changes["params_schema"]  # type: ignore[assignment]
    if "output_schema" in changes and changes["output_schema"] is not None:
        tool.output_schema = changes["output_schema"]  # type: ignore[assignment]
    if (integration_id := changes.get("integration_id")) is not None:
        _get_active_integration(session, integration_id)  # type: ignore[arg-type]
        tool.integration_id = integration_id  # type: ignore[assignment]

    tool.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(tool)
    return tool


def delete_catalog_tool(session: Session, tool_id: uuid.UUID, *, principal: Principal) -> None:
    """Soft-delete a `kind="integration"` catalog tool. Builder role required.

    Built-in tools (`kind="builtin"`) can never be deleted through the API.
    """
    require_builder(principal)
    tool = get_catalog_tool(session, tool_id)
    if tool.kind == "builtin":
        raise ValidationError("Built-in tools cannot be deleted", code="builtin_tool_immutable")

    tool.is_deleted = True
    tool.deleted_at = datetime.now(UTC)
    session.commit()


def seed_default_tools(
    session: Session, *, tenant_id: uuid.UUID, owner_id: uuid.UUID
) -> dict[str, Tool]:
    """Idempotently seed the built-in catalog for a tenant; return by tool_type."""
    from app.core.ids import uuid7

    result: dict[str, Tool] = {}
    for spec in DEFAULT_TOOL_SPECS:
        existing = session.execute(
            select(Tool).where(
                Tool.tool_type == spec["tool_type"], Tool.is_deleted.is_(False)
            )
        ).scalars().first()
        if existing is not None:
            result[spec["tool_type"]] = existing
            continue
        tool = Tool(
            id=uuid7(),
            tenant_id=tenant_id,
            owner_id=owner_id,
            tool_type=spec["tool_type"],
            kind="builtin",
            display_name=spec["display_name"],
            description=spec["description"],
            params_schema=spec["params_schema"],
            output_schema=spec["output_schema"],
            config=spec["config"],
        )
        session.add(tool)
        result[spec["tool_type"]] = tool
    session.commit()
    for tool in result.values():
        session.refresh(tool)
    return result
