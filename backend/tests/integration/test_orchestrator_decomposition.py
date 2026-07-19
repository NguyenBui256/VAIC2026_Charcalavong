"""Integration tests for `list_routable_agents` (Task 3) and LLM
decomposition `decompose_run` (Story 3.3, Task 4).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import AdminSessionLocal
from app.core.ports.llm import CompletionResult
from app.core.tenant_context import set_tenant_session_var, tenant_context
from app.modules.agent_builder.models import Agent
from app.modules.agent_builder.service import list_routable_agents
from app.modules.orchestrator.models import Workflow, WorkflowRun


def _as_app(session: Session, tenant_id) -> None:
    """Drop superuser privileges + set RLS context for the current txn.

    Also sets the `tenant_context` contextvar (mirrors `test_kb_api.py`) --
    `decompose_run`/`execute_task_row`/`orchestrate_run` re-assert RLS via
    `tenant_context.get()` after every internal CAS commit (AD-10), and
    `PostgresAuditSink.log()` reads the same contextvar to scope its INSERT.
    """
    tenant_context.set(tenant_id)
    session.execute(text("SET LOCAL ROLE vaic_app"))
    set_tenant_session_var(session, tenant_id)


def test_list_routable_agents_shape(app_session: Session, seeded_agent: dict[str, Any]) -> None:
    _as_app(app_session, seeded_agent["tenant_agents_id"])
    rows = list_routable_agents(app_session)
    assert isinstance(rows, list)
    if rows:
        assert set(rows[0]) == {"id", "name", "department_id", "system_prompt"}


class FakeLlm:
    """Deterministic `LlmPort.complete` stand-in — no live API key needed."""

    def __init__(self, payload: list[dict]) -> None:
        self._payload = payload

    def complete(self, messages, model, parameters=None) -> CompletionResult:
        return CompletionResult(content=json.dumps(self._payload), model="fake", latency_ms=1)


@pytest.fixture()
def seeded_run_with_two_agents(
    app_session: Session, agent_seed_data: dict[str, Any]
) -> Iterator[tuple[WorkflowRun, uuid.UUID, uuid.UUID]]:
    """Seed 2 Agents + a Workflow + a `running` Run, all in the same tenant.

    Uses `AdminSessionLocal` for the seed writes (bypasses RLS) so the test
    body's `app_session` only needs read/CAS access, mirroring `seeded_agent`.
    Cleaned up after the test via `AdminSessionLocal` (decompose_run/
    execute_task_row commit for real — the `app_session` fixture's rollback
    does not undo them).
    """
    tenant_id = agent_seed_data["tenant_agents_id"]
    dept_id = agent_seed_data["dept_agents_id"]
    owner_id = agent_seed_data["builder_user_id"]
    agent_a_id, agent_b_id = uuid.uuid4(), uuid.uuid4()
    workflow_id, run_id = uuid.uuid4(), uuid.uuid4()

    with AdminSessionLocal() as s:
        s.add(Agent(id=agent_a_id, tenant_id=tenant_id, department_id=dept_id,
                     owner_id=owner_id, name="Screener", system_prompt="You screen credit."))
        s.add(Agent(id=agent_b_id, tenant_id=tenant_id, department_id=dept_id,
                     owner_id=owner_id, name="Reviewer", system_prompt="You review docs."))
        s.add(Workflow(id=workflow_id, tenant_id=tenant_id, owner_id=owner_id,
                        name="Loan Review", description="Screen and review a loan application."))
        s.flush()
        s.add(WorkflowRun(id=run_id, tenant_id=tenant_id, workflow_id=workflow_id,
                           status="running"))
        s.commit()
        run = s.get(WorkflowRun, run_id)
        s.expunge(run)

    _as_app(app_session, tenant_id)
    try:
        yield run, agent_a_id, agent_b_id
    finally:
        with AdminSessionLocal() as s:
            s.execute(text("DELETE FROM tasks WHERE run_id=:id"), {"id": str(run_id)})
            s.execute(text("DELETE FROM audit_trail WHERE run_id=:id"), {"id": str(run_id)})
            s.execute(text("DELETE FROM workflow_runs WHERE id=:id"), {"id": str(run_id)})
            s.execute(text("DELETE FROM workflows WHERE id=:id"), {"id": str(workflow_id)})
            s.execute(text("DELETE FROM agents WHERE id IN (:a, :b)"),
                      {"a": str(agent_a_id), "b": str(agent_b_id)})
            s.commit()


def test_decompose_inserts_valid_rejects_unknown(
    app_session: Session, seeded_run_with_two_agents: tuple[WorkflowRun, uuid.UUID, uuid.UUID]
) -> None:
    from app.modules.orchestrator.service import decompose_run

    run, agent_a_id, _agent_b_id = seeded_run_with_two_agents
    payload = [
        {"task": {"summary": "screen credit"}, "target_agent_id": str(agent_a_id),
         "input": {"x": 1}, "output": {"type": "object"}, "expected": ["do it"], "criteria": {}},
        {"task": {"summary": "bogus"}, "target_agent_id": str(uuid.uuid4()),
         "input": {}, "output": {}, "expected": [], "criteria": {}},
    ]
    tasks = decompose_run(app_session, run.id, llm=FakeLlm(payload))
    assert len(tasks) == 1
    assert str(tasks[0].target_agent_id) == str(agent_a_id)
    assert tasks[0].status == "pending"


def test_decompose_run_is_idempotent(
    app_session: Session, seeded_run_with_two_agents: tuple[WorkflowRun, uuid.UUID, uuid.UUID]
) -> None:
    """Second `decompose_run` call for the same Run must not call the LLM or
    insert duplicate Tasks (resume-path safety, AC8 carry-forward)."""
    from app.modules.orchestrator.service import decompose_run

    run, agent_a_id, _agent_b_id = seeded_run_with_two_agents
    payload = [
        {"task": {"summary": "screen credit"}, "target_agent_id": str(agent_a_id),
         "input": {}, "output": {}, "expected": [], "criteria": {}},
    ]
    first = decompose_run(app_session, run.id, llm=FakeLlm(payload))
    assert len(first) == 1

    class ExplodingLlm:
        def complete(self, *a, **k):
            raise AssertionError("LLM must not be called on a re-entrant decompose_run")

    second = decompose_run(app_session, run.id, llm=ExplodingLlm())
    assert [t.id for t in second] == [t.id for t in first]

    _as_app(app_session, run.tenant_id)
    count = app_session.execute(
        text("SELECT count(*) FROM tasks WHERE run_id=:id"), {"id": str(run.id)}
    ).scalar_one()
    assert count == 1
