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
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

__all__ = ["AgentProviderPort", "RetrievalPassage", "TaskExecutionResult"]


class RetrievalPassage(BaseModel):
    """A single cited passage returned from a Knowledge Base retrieval (AC3).

    Field names are exact -- the Orchestrator and citation rendering depend
    on them. DO NOT rename.
    """

    passage: str
    document_name: str
    chunk_reference: str
    score: float


class TaskExecutionResult(BaseModel):
    """Result of dispatching one Orchestrator Task to a Specialist Agent.

    Produced by `AgentProviderPort.execute_task` (Story 3.3/3.4 concrete
    implementation: `app/modules/agent_builder/agent_executor.py`).
    """

    output: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    kb_citations: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    rationale: str = ""
    success: bool = True
    error: str = ""


@runtime_checkable
class AgentProviderPort(Protocol):
    """Hexagonal port for Agent-internal capabilities dispatched at runtime.

    Implementation: `app/modules/agent_builder/kb_retrieval.py` (`kb_search`
    wired behind `retrieve`); `app/modules/agent_builder/agent_executor.py`
    (`execute_task`, Story 3.3/3.4).
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

    async def execute_task(
        self,
        agent_id: uuid.UUID,
        task_payload: dict[str, Any],
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> TaskExecutionResult:
        """Run the Specialist Agent's prompt+model (+KB, +Tool) for one Task."""
        ...
