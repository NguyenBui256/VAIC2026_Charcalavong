"""Per-agent KB document grants (the tick) — Sub-project A (spec D3, revised).

Invariant: a row may only be created by a user who can edit the agent
(builder, or owns/same-dept per `_authorize_mutation`). Doc pool is
builder-managed tenant-wide (no per-user grants). `list_agent_document_ids`
is the runtime scope source for two-gate RAG (`kb_retrieval`).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenant_context import tenant_context
from app.modules.agent_builder.kb_models import AgentKbDocument, KbDocument
from app.modules.agent_builder.kb_service import _get_document_row
from app.modules.agent_builder.service import Principal, _authorize_mutation, get_agent

__all__ = [
    "list_agent_documents", "attach_agent_document",
    "detach_agent_document", "list_agent_document_ids",
]


def list_agent_documents(session: Session, *, agent_id: uuid.UUID) -> list[KbDocument]:
    return list(
        session.execute(
            select(KbDocument)
            .join(AgentKbDocument, AgentKbDocument.document_id == KbDocument.id)
            .where(AgentKbDocument.agent_id == agent_id)
            .order_by(KbDocument.filename)
        ).scalars().all()
    )


def list_agent_document_ids(session: Session, agent_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        session.execute(
            select(AgentKbDocument.document_id).where(AgentKbDocument.agent_id == agent_id)
        ).scalars().all()
    )


def attach_agent_document(
    session: Session, *, agent_id: uuid.UUID, document_id: uuid.UUID, principal: Principal
) -> None:
    """Tick a doc into an agent. Requires edit-on-agent (builder or owns/same-dept)."""
    agent = get_agent(session, agent_id)
    _authorize_mutation(agent, principal)          # can edit this agent
    _get_document_row(session, document_id)        # doc must exist (tenant-scoped by RLS)
    existing = session.get(AgentKbDocument, {"agent_id": agent_id, "document_id": document_id})
    if existing is not None:
        return
    session.add(AgentKbDocument(
        agent_id=agent_id, document_id=document_id, tenant_id=tenant_context.get()
    ))
    session.commit()


def detach_agent_document(
    session: Session, *, agent_id: uuid.UUID, document_id: uuid.UUID, principal: Principal
) -> None:
    agent = get_agent(session, agent_id)
    _authorize_mutation(agent, principal)
    row = session.get(AgentKbDocument, {"agent_id": agent_id, "document_id": document_id})
    if row is not None:
        session.delete(row)
        session.commit()
