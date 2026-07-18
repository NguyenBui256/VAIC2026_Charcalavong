"""Knowledge Base runtime retrieval (Story 2.5).

`kb_search` is the Agent-internal retrieval function the Orchestrator
(Epic 3) dispatches to via `AgentProviderPort.retrieve`. It derives its
`tenant_id`/`department_id` scope from the Agent record itself (Story 2.1)
-- NEVER from a caller-supplied argument (FR-2): a caller cannot request
another Department's KB because it cannot supply the Department.

Routes through `McpClientPort.call_tool("rag.search", ...)` (AD-3). The
`McpClientPort` implementation enforces the AD-11 client-side department
scope check and RAISES `AuthorizationError` before the network on mismatch;
this module surfaces that raise -- it never swallows it (AC2).

Every retrieval is logged to `audit_trail` via `AuditPort` (AD-4) with
`type="kb.retrieval"`, aggregating `passage_count`/`top_score` only -- never
passage text (keeps the audit trail lean, avoids logging document content).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.deps import crud_audit_ids, get_mcp_client
from app.core.ids import utcnow_iso_ms
from app.core.ports.agent_provider import AgentProviderPort, RetrievalPassage
from app.core.ports.audit import AuditEntry, AuditPort
from app.core.ports.mcp_client import McpClientPort
from app.modules.agent_builder.models import Agent
from app.modules.agent_builder.service import get_agent as get_agent_row

__all__ = ["kb_search", "AgentKbProvider"]

McpFactory = Callable[..., McpClientPort]
AgentLoader = Callable[[Session, uuid.UUID], Agent]


def _map_passages(raw: list[dict]) -> list[RetrievalPassage]:
    """Map MCP `rag.search` output into `RetrievalPassage` entries (AC3, AC4).

    An empty/absent `passages` list maps to `[]` -- covers the un-indexed and
    cross-department cases identically (both are legitimately empty).
    """
    return [
        RetrievalPassage(
            passage=item.get("passage", ""),
            document_name=item.get("document_name", ""),
            chunk_reference=item.get("chunk_reference", ""),
            score=float(item.get("score", 0.0)),
        )
        for item in raw
    ]


def _emit_retrieval_audit(
    audit: AuditPort, agent: Agent, query: str, passages: list[RetrievalPassage]
) -> None:
    """Emit exactly one `kb.retrieval` audit entry -- aggregates only (AC5).

    `output` is `{passage_count, top_score}` -- never passage text (mirrors
    the NFR-9 lean-audit convention from Story 2.4).
    """
    run_id, step_id = crud_audit_ids(str(agent.id))
    top_score = max((p.score for p in passages), default=None)
    audit.log(
        AuditEntry(
            run_id=run_id,
            step_id=step_id,
            agent_id=str(agent.id),
            ts=utcnow_iso_ms(),
            type="kb.retrieval",
            input={"agent_id": str(agent.id), "query": query},
            output={"passage_count": len(passages), "top_score": top_score},
            latency_ms=0,
            model="",
        )
    )


async def kb_search(
    session: Session,
    agent_id: uuid.UUID,
    query: str,
    *,
    top_k: int = 5,
    mcp_factory: McpFactory = get_mcp_client,
    audit: AuditPort | None = None,
    agent_loader: AgentLoader = get_agent_row,
) -> list[RetrievalPassage]:
    """Two-gate KB retrieval (spec D3).

    Gate 1: the agent must reference the `rag` tool. Gate 2: it must have
    granted documents. `rag.search` is scoped to exactly those documents;
    scope is derived from `agent_kb_documents`, never caller-supplied.
    """
    from app.modules.agent_builder.agent_kb_service import list_agent_document_ids
    from app.modules.agent_builder.tool_catalog_service import list_agent_tool_refs

    agent = agent_loader(session, agent_id)

    has_rag = any(t.tool_type == "rag" for t in list_agent_tool_refs(session, agent_id=agent_id))
    if not has_rag:
        return []
    doc_ids = [str(d) for d in list_agent_document_ids(session, agent_id)]
    if not doc_ids:
        return []

    mcp = mcp_factory(agent_department_id=agent.department_id)
    result = await mcp.call_tool(
        "rag.search",
        {
            "agent_id": str(agent.id),
            "query": query,
            "document_ids": doc_ids,
            "tenant_id": str(agent.tenant_id),
            "department_id": str(agent.department_id),
        },
        tenant_id=agent.tenant_id,
        department_id=agent.department_id,
    )
    passages = _map_passages(result.output.get("passages", []))
    _emit_retrieval_audit(audit or PostgresAuditSink(), agent, query, passages)
    return passages


class AgentKbProvider(AgentProviderPort):
    """Concrete `AgentProviderPort` adapter dispatching to `kb_search` (AC6).

    `tenant_id`/`department_id` are accepted on `retrieve` for structural
    compliance with the AD-11 keyword-only convention mirrored across ports,
    but they are NEVER used to override the Agent's own scope -- `kb_search`
    re-derives it from the Agent record on every call (FR-2, anti-pattern #1).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    async def retrieve(
        self,
        agent_id: uuid.UUID,
        query: str,
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
        top_k: int = 5,
    ) -> list[RetrievalPassage]:
        """Dispatch to `kb_search`; scope is re-derived, never overridden."""
        _ = tenant_id, department_id  # accepted for Protocol compliance only
        return await kb_search(self._session, agent_id, query, top_k=top_k)
