"""Concrete `AgentProviderPort`: runs a Specialist Agent's prompt+model+KB+Tool
for one Orchestrator Task (Story 3.3/3.4 Task 2).

Composes existing, already-tested collaborators -- never re-implements them:
`get_agent`/`invoke_agent_model` (agent_builder.service), `AgentKbProvider`
(department-scoped KB retrieval, agent_builder.kb_retrieval), `get_tool_by_name`
/`invoke_tool` (agent_builder.tool_service). AD-1: orchestrator dispatches to
this module through the `AgentProviderPort` interface only.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.ports.agent_provider import (
    AgentProviderPort,
    RetrievalPassage,
    TaskExecutionResult,
)
from app.modules.agent_builder.kb_retrieval import AgentKbProvider
from app.modules.agent_builder.service import get_agent, invoke_agent_model
from app.modules.agent_builder.tool_service import get_tool_by_name, invoke_tool

__all__ = ["AgentExecutor"]


def _build_prompt(task_payload: dict[str, Any], passages: list[RetrievalPassage]) -> str:
    """Compose the run-time prompt from the Task payload + KB citations."""
    cites = "\n".join(f"- [{p.document_name}#{p.chunk_reference}] {p.passage}" for p in passages)
    return (
        f"TASK: {task_payload.get('task', {}).get('summary', '')}\n"
        f"INPUT: {json.dumps(task_payload.get('input', {}), ensure_ascii=False)}\n"
        f"EXPECTED STEPS: {task_payload.get('expected', [])}\n"
        f"KB CONTEXT:\n{cites or '(none)'}\n\n"
        'Respond ONLY with a JSON object matching the task output schema. '
        'Include a numeric field "confidence" in [0,1] and a "rationale" string.'
    )


def _parse_output(content: str) -> tuple[dict[str, Any], float, str]:
    """Parse the model's JSON reply; fall back to wrapping raw text (demo-safe)."""
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data, float(data.get("confidence", 1.0)), str(data.get("rationale", ""))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return {"raw": content}, 1.0, ""


class AgentExecutor(AgentProviderPort):
    """Runs one Task against a Specialist Agent's prompt+model(+KB, +Tool)."""

    def __init__(self, session: Session, *, audit: Any | None = None) -> None:
        self._session = session
        self._audit = audit
        self._kb = AgentKbProvider(session)

    async def retrieve(
        self,
        agent_id: uuid.UUID,
        query: str,
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
        top_k: int = 5,
    ) -> list[RetrievalPassage]:
        return await self._kb.retrieve(
            agent_id, query, tenant_id=tenant_id, department_id=department_id, top_k=top_k
        )

    async def execute_task(
        self,
        agent_id: uuid.UUID,
        task_payload: dict[str, Any],
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> TaskExecutionResult:
        agent = get_agent(self._session, agent_id)
        query = task_payload.get("task", {}).get("summary", "") or str(
            task_payload.get("input", "")
        )
        passages = await self._kb.retrieve(
            agent_id, query, tenant_id=tenant_id, department_id=department_id
        )
        completion = invoke_agent_model(
            agent, _build_prompt(task_payload, passages), audit=self._audit
        )
        output, confidence, rationale = _parse_output(completion.content)
        tool_calls = self._run_required_tool(agent_id, task_payload, tenant_id, department_id)
        return TaskExecutionResult(
            output=output,
            confidence=confidence,
            rationale=rationale,
            tool_calls=tool_calls,
            kb_citations=[f"{p.document_name}#{p.chunk_reference}" for p in passages],
        )

    def _run_required_tool(
        self,
        agent_id: uuid.UUID,
        task_payload: dict[str, Any],
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """If `criteria.must_use_tool` names a Tool, invoke it and record the call."""
        tool_name = task_payload.get("criteria", {}).get("must_use_tool")
        if not tool_name:
            return []
        tool = get_tool_by_name(self._session, agent_id=agent_id, display_name=tool_name)
        out = invoke_tool(
            self._session,
            tool,
            task_payload.get("input", {}),
            tenant_id=tenant_id,
            department_id=department_id,
            audit=self._audit,
        )
        return [{"tool": tool_name, "output": out.output, "success": out.success}]
