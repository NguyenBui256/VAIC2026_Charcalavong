"""AgentProviderPort -- hexagonal port for Agent-internal capabilities the
Orchestrator dispatches to (Story 2.5, deferred from Story 1.4).

Story 1.4 explicitly deferred this port (see `1-4-...md` L68). Story 2.5
creates it to expose the Knowledge Base retrieval capability (`kb_search`)
so the Orchestrator (Epic 3) can dispatch retrieval Tasks to Specialist
Agents without depending on a concrete class (hexagonal boundary, AD-1).

Per AD-11: `retrieve` is scoped by keyword-only `tenant_id` + `department_id`,
mirroring the `McpClientPort`/`DocIntakePort` convention. The concrete
implementation (`app/modules/agent_builder/kb_retrieval.py`) NEVER uses a
caller-supplied scope to override the Agent's own Department -- it re-derives
scope from the Agent record on every call (FR-2).
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

__all__ = ["AgentProviderPort", "RetrievalPassage"]


class RetrievalPassage(BaseModel):
    """A single cited passage returned from a Knowledge Base retrieval (AC3).

    Field names are exact -- the Orchestrator and citation rendering depend
    on them. DO NOT rename.
    """

    passage: str
    document_name: str
    chunk_reference: str
    score: float


@runtime_checkable
class AgentProviderPort(Protocol):
    """Hexagonal port for Agent-internal capabilities dispatched at runtime.

    Implementation: `app/modules/agent_builder/kb_retrieval.py` (`kb_search`
    wired behind `retrieve`).
    """

    async def retrieve(
        self,
        agent_id: uuid.UUID,
        query: str,
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
        top_k: int = 5,
    ) -> list[RetrievalPassage]:
        """Retrieve cited passages from the Agent's own Knowledge Base.

        Per FR-2: scope MUST be the Agent's own `department_id` -- never
        caller-supplied. A wrong-department retrieval returns `[]`, never
        another Department's documents (AD-11).
        """
        ...
