"""Tool CRUD service — register/list/update/soft-delete Tools (Story 2.6 T5).

Mirrors the Story 2.1 `agents` CRUD conventions verbatim: `tenant_context`
via RLS (never accept `tenant_id` as an argument), builder-role + owner-or-
same-department authz reused from `service._authorize_mutation`, soft-delete
only, and one `audit.log()` per write (AD-4).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.deps import crud_audit_ids
from app.core.ids import utcnow_iso_ms, uuid7
from app.core.ports.audit import AuditEntry, AuditPort
from app.core.tenant_context import tenant_context
from app.modules.agent_builder.models import Tool
from app.modules.agent_builder.schema_validation import validate_schema_document
from app.modules.agent_builder.service import Principal, _authorize_mutation
from app.modules.agent_builder.service import get_agent as get_agent_row
from app.modules.agent_builder.tool_service import get_tool

__all__ = [
    "create_tool",
    "list_tools",
    "update_tool",
    "soft_delete_tool",
    "serialize_tool",
]


def _emit_tool_audit(audit: AuditPort, tool: Tool, entry_type: str) -> None:
    """Emit one CRUD audit entry (AD-4). NEVER includes the raw `header` secret."""
    run_id, step_id = crud_audit_ids(str(tool.id))
    payload = {
        "tool_id": str(tool.id),
        "agent_id": str(tool.agent_id),
        "display_name": tool.display_name,
    }
    audit.log(
        AuditEntry(
            run_id=run_id,
            step_id=step_id,
            agent_id=str(tool.agent_id),
            ts=utcnow_iso_ms(),
            type=entry_type,
            input=payload,
            output=payload,
            latency_ms=0,
            model="",
        )
    )


def create_tool(
    session: Session,
    *,
    agent_id: uuid.UUID,
    principal: Principal,
    display_name: str,
    header: dict[str, Any],
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    embedded_python: str | None = None,
    audit: AuditPort | None = None,
) -> Tool:
    """Register a Tool against an Agent (AC1). Rejects malformed schemas."""
    agent = get_agent_row(session, agent_id)
    _authorize_mutation(agent, principal)

    validate_schema_document(input_schema)
    validate_schema_document(output_schema)

    tool = Tool(
        id=uuid7(),
        agent_id=agent.id,
        tenant_id=tenant_context.get(),
        department_id=agent.department_id,
        display_name=display_name,
        header=header,
        input_schema=input_schema,
        output_schema=output_schema,
        embedded_python=embedded_python,
    )
    session.add(tool)
    session.commit()
    session.refresh(tool)

    _emit_tool_audit(audit or PostgresAuditSink(), tool, "tool.created")
    return tool


def list_tools(session: Session, *, agent_id: uuid.UUID) -> list[Tool]:
    """List non-deleted Tools for an Agent. Tenant scoping is RLS-only."""
    return list(
        session.execute(
            select(Tool).where(Tool.agent_id == agent_id, Tool.is_deleted.is_(False))
        )
        .scalars()
        .all()
    )


def update_tool(
    session: Session,
    *,
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    principal: Principal,
    audit: AuditPort | None = None,
    **changes: object,
) -> Tool:
    """Update mutable fields on a Tool (mirrors `service.update_agent`)."""
    tool = get_tool(session, agent_id=agent_id, tool_id=tool_id)
    agent = get_agent_row(session, agent_id)
    _authorize_mutation(agent, principal)

    allowed_fields = {"display_name", "header", "input_schema", "output_schema", "embedded_python"}
    for key, value in changes.items():
        if key not in allowed_fields or value is None:
            continue
        if key in {"input_schema", "output_schema"}:
            validate_schema_document(value)  # type: ignore[arg-type]
        setattr(tool, key, value)

    tool.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(tool)

    _emit_tool_audit(audit or PostgresAuditSink(), tool, "tool.updated")
    return tool


def soft_delete_tool(
    session: Session,
    *,
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    principal: Principal,
    audit: AuditPort | None = None,
) -> None:
    """Soft-delete a Tool — never hard-deletes. Symmetric authz with create (AD-11 parity)."""
    tool = get_tool(session, agent_id=agent_id, tool_id=tool_id)
    agent = get_agent_row(session, agent_id)
    _authorize_mutation(agent, principal)

    tool.is_deleted = True
    tool.deleted_at = datetime.now(UTC)
    session.commit()
    session.refresh(tool)

    _emit_tool_audit(audit or PostgresAuditSink(), tool, "tool.deleted")


def serialize_tool(tool: Tool) -> dict:
    """Response payload — `header` masked, never echoed in full (NFR-9)."""
    return {
        "id": str(tool.id),
        "agent_id": str(tool.agent_id),
        "display_name": tool.display_name,
        "header": {"auth": bool(tool.header.get("auth"))} if tool.header else {},
        "input_schema": tool.input_schema,
        "output_schema": tool.output_schema,
        "has_embedded_python": tool.embedded_python is not None,
        "kind": "embedded_python" if tool.embedded_python else "mcp",
        "created_at": tool.created_at.isoformat(timespec="milliseconds"),
        "updated_at": tool.updated_at.isoformat(timespec="milliseconds"),
    }
