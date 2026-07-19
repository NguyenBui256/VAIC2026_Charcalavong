# Epic 3 — Story 3.3 + 3.4: Decomposition, Agent Task Execution & Aggregation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`).
>
> **Bash policy (user rule):** NEVER run bash in the main session. Delegate every shell command (alembic, pytest, ruff) to a subagent. Do NOT commit/push without explicit user consent.

**Goal:** After a Workflow Run reaches `running` (Story 3.2), the Orchestrator LLM-decomposes the request into ≤5 schema-valid Tasks, dispatches each to its target Specialist Agent (running that Agent's system prompt + model + Tools + KB), then aggregates all results into the Run — delivering SHB rubric bars 1 (specialist collaboration), 2 (planner decomposition), 3 (real tool use), and the audit stream Trace (bar 4) reads.

**Architecture:** Extends the `orchestrator` module (Stories 3.1/3.2 land the `workflows`/`workflow_runs`/`tasks` tables, models, CAS helpers, and the `run_workflow` arq worker first). This plan adds: (a) `AgentProviderPort.execute_task` + a concrete `AgentExecutor` in `agent_builder` that composes the existing `invoke_agent_model` + `AgentKbProvider.retrieve` + `tool_service.invoke_tool`; (b) a public agent selector for routing; (c) `orchestrator.service` decomposition + sequential task execution + aggregation, wired into the `run_workflow` worker body. Task execution is **sequential** in the worker (demo-safe) but every state change still uses compare-and-set (AD-6). Concurrent claim-pool = DEFER.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x (sync), Pydantic 2.x, arq/Redis, Postgres 18 (RLS). Same pins as Epic 2 — no new deps.

## Global Constraints

- **Prereq (HARD GATE):** Stories 3.1 + 3.2 MUST be green before this plan runs. This plan consumes: `Workflow`, `WorkflowRun`, `Task` models; `transition_run_status`, `transition_task_status` CAS helpers; the `run_workflow(ctx, ...)` arq worker; `tasks.status ∈ {pending,claimed,completed,failed}`; `workflow_runs.status ∈ {pending,running,awaiting_human,completed,failed,timed_out}`.
- **AD-1 (module boundary):** orchestrator NEVER imports `agent_builder` models. It calls `agent_builder` public service functions only. The one sanctioned cross-module coupling is the DB-level FK `tasks.target_agent_id → agents.id`.
- **AD-4 (audit):** `PostgresAuditSink().log(AuditEntry(...))` is the only path to `audit_trail`; failure RAISES and crashes the Run (never swallow). Run-scoped steps use REAL `run_id=str(run.id)` + `step_id=str(uuid7())` — NOT the `crud_audit_ids` stopgap.
- **AD-6 (CAS):** every `tasks.status` / `workflow_runs.status` change goes through the `transition_*_status` helpers; caller checks the returned bool; `False` (lost race / wrong prior state) → clean return, never proceed.
- **AD-10 (tenant across arq):** worker functions use `@tenant_aware_job`; enqueue via `enqueue_job_with_context(pool, name, **kwargs)` which injects `_tenant_id`. Inside the worker, `tenant_context` + session tenant GUC are already set by the decorator before the body runs.
- **KB is department-scoped, NOT agent-scoped.** `Agent` has no `kb_id`. Retrieval is routed by `department_id`.
- **IDs:** `from app.core.ids import uuid7, utcnow_iso_ms`. UUID v7 only.
- **Function size ceiling:** 50 lines. Naming: Python `snake_case`; React `PascalCase`.
- **max_tasks ceiling = 5** (R2 mitigation). Orchestrator LLM temperature ≤ 0.3.
- **TDD:** RED → GREEN each task. DoD: test `file:line` PASSED + production `file:line`.
- **Test/lint commands (delegate to subagent, cwd=`backend/`):** `uv run pytest <path> -v` · `uv run ruff check app tests`.

---

## File Structure

- `backend/app/core/ports/agent_provider.py` — MODIFY: add `TaskExecutionResult` + `execute_task` to the Protocol.
- `backend/app/modules/agent_builder/agent_executor.py` — CREATE: `AgentExecutor(AgentProviderPort)` — implements both `retrieve` (delegate to existing `AgentKbProvider`) and new `execute_task`.
- `backend/app/modules/agent_builder/service.py` — MODIFY: add `list_routable_agents(session)` public selector.
- `backend/app/modules/orchestrator/service.py` — MODIFY (built in 3.1/3.2): add `decompose_run`, `execute_task_row`, `aggregate_run`, `orchestrate_run`, `_orchestrator_llm`.
- `backend/app/modules/orchestrator/schemas.py` — CREATE (if not from 3.1): `TaskSchemaModel` Pydantic validator for the Task Schema.
- `backend/app/modules/orchestrator/jobs.py` or worker body — MODIFY: `run_workflow` body calls `orchestrate_run` after `pending→running`.
- `backend/tests/integration/test_orchestrator_decomposition.py` — CREATE.
- `backend/tests/integration/test_orchestrator_execution.py` — CREATE.
- `backend/tests/unit/test_agent_executor.py` — CREATE.
- Frontend (outline only, §Task 8): `frontend/src/pages/workflow-runs.tsx`, `frontend/src/pages/workflow-run-detail.tsx`.

---

## Task 1: Extend `AgentProviderPort` with `execute_task`

**Files:**
- Modify: `backend/app/core/ports/agent_provider.py`
- Test: `backend/tests/unit/test_agent_executor.py`

**Interfaces:**
- Consumes: existing `RetrievalPassage`, `AgentProviderPort.retrieve` (in same file).
- Produces: `TaskExecutionResult` (Pydantic) + `AgentProviderPort.execute_task(agent_id, task_payload, *, tenant_id, department_id) -> TaskExecutionResult`. Task 2 implements it; Tasks 4–6 consume it.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_agent_executor.py
from app.core.ports.agent_provider import TaskExecutionResult, AgentProviderPort

def test_task_execution_result_defaults():
    r = TaskExecutionResult(output={"verdict": "pass"})
    assert r.success is True
    assert r.confidence == 1.0
    assert r.tool_calls == []
    assert r.kb_citations == []

def test_execute_task_in_protocol():
    assert hasattr(AgentProviderPort, "execute_task")
```

- [ ] **Step 2: Run test to verify it fails**

Run (subagent): `uv run pytest tests/unit/test_agent_executor.py -v`
Expected: FAIL — `ImportError: cannot import name 'TaskExecutionResult'`.

- [ ] **Step 3: Add the type + protocol method**

```python
# append to backend/app/core/ports/agent_provider.py

class TaskExecutionResult(BaseModel):
    output: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    kb_citations: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    rationale: str = ""
    success: bool = True
    error: str = ""


# inside class AgentProviderPort(Protocol): add this method
    async def execute_task(
        self,
        agent_id: uuid.UUID,
        task_payload: dict[str, Any],
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> "TaskExecutionResult": ...
```

Ensure `from typing import Any` and `from pydantic import BaseModel, Field` are imported at top (add if missing).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_agent_executor.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit** (only with user consent — otherwise stage locally per policy)

```
git add backend/app/core/ports/agent_provider.py backend/tests/unit/test_agent_executor.py
git commit -m "feat(orchestrator): add execute_task to AgentProviderPort"
```

---

## Task 2: Concrete `AgentExecutor.execute_task`

**Files:**
- Create: `backend/app/modules/agent_builder/agent_executor.py`
- Test: `backend/tests/unit/test_agent_executor.py` (extend)

**Interfaces:**
- Consumes: `get_agent`, `invoke_agent_model` (`agent_builder/service.py`); `AgentKbProvider` (`agent_builder/kb_retrieval.py`); `invoke_tool`, `get_tool` (`agent_builder/tool_service.py`); `CompletionResult` (`core/ports/llm.py`); `TaskExecutionResult` (Task 1).
- Produces: `class AgentExecutor` with ctor `AgentExecutor(session, *, audit=None)`; `async execute_task(...)`, `async retrieve(...)`. Task 5 consumes it.

**Behavior (demo-safe):** retrieve KB passages (dept-scoped) → build a prompt from `task_payload` (summary/input/expected/criteria) + injected citations → `invoke_agent_model` → parse JSON output (fallback: wrap raw text) → if `criteria.must_use_tool` present, invoke that Tool with `task_payload["input"]` and attach to `tool_calls` → assemble `TaskExecutionResult` (confidence from parsed JSON `confidence` else 1.0).

- [ ] **Step 1: Write the failing test** (uses monkeypatched collaborators — no live LLM)

```python
# extend backend/tests/unit/test_agent_executor.py
import uuid, pytest
from app.core.ports.llm import CompletionResult
from app.core.ports.agent_provider import TaskExecutionResult

@pytest.mark.asyncio
async def test_execute_task_composes_model_and_kb(monkeypatch):
    from app.modules.agent_builder import agent_executor as mod

    fake_agent = type("A", (), {"id": uuid.uuid4(), "system_prompt": "You are Credit Analyst",
                               "department_id": uuid.uuid4(), "model": {"provider": "anthropic", "model_name": "x"}})()
    monkeypatch.setattr(mod, "get_agent", lambda s, aid: fake_agent)
    monkeypatch.setattr(mod, "invoke_agent_model",
                        lambda agent, prompt, **k: CompletionResult(
                            content='{"verdict":"pass","confidence":0.9}', model="x", latency_ms=5))

    class FakeKb:
        def __init__(self, s): ...
        async def retrieve(self, aid, q, *, tenant_id, department_id, top_k=5):
            from app.core.ports.agent_provider import RetrievalPassage
            return [RetrievalPassage(passage="policy clause", document_name="lending.pdf",
                                     chunk_reference="c1", score=0.8)]
    monkeypatch.setattr(mod, "AgentKbProvider", FakeKb)

    ex = mod.AgentExecutor(session=None)
    res = await ex.execute_task(fake_agent.id, {"task": {"summary": "screen loan"},
                                "input": {"revenue": 1}, "expected": [], "criteria": {}},
                                tenant_id=uuid.uuid4(), department_id=fake_agent.department_id)
    assert isinstance(res, TaskExecutionResult)
    assert res.success is True
    assert res.output.get("verdict") == "pass"
    assert res.confidence == 0.9
    assert "lending.pdf" in res.kb_citations[0]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/unit/test_agent_executor.py::test_execute_task_composes_model_and_kb -v`
Expected: FAIL — module `agent_executor` missing.

- [ ] **Step 3: Implement `AgentExecutor`**

```python
# backend/app/modules/agent_builder/agent_executor.py
"""Concrete AgentProviderPort: runs a Specialist Agent's prompt+model+KB+Tool for one Task."""
from __future__ import annotations

import json
import uuid
from typing import Any

from app.core.ports.agent_provider import AgentProviderPort, RetrievalPassage, TaskExecutionResult
from app.modules.agent_builder.kb_retrieval import AgentKbProvider
from app.modules.agent_builder.service import get_agent, invoke_agent_model
from app.modules.agent_builder.tool_service import get_tool, invoke_tool


def _build_prompt(task_payload: dict[str, Any], passages: list[RetrievalPassage]) -> str:
    cites = "\n".join(f"- [{p.document_name}#{p.chunk_reference}] {p.passage}" for p in passages)
    return (
        f"TASK: {task_payload.get('task', {}).get('summary', '')}\n"
        f"INPUT: {json.dumps(task_payload.get('input', {}), ensure_ascii=False)}\n"
        f"EXPECTED STEPS: {task_payload.get('expected', [])}\n"
        f"KB CONTEXT:\n{cites or '(none)'}\n\n"
        "Respond ONLY with a JSON object matching the task output schema. "
        "Include a numeric field \"confidence\" in [0,1] and a \"rationale\" string."
    )


def _parse_output(content: str) -> tuple[dict[str, Any], float, str]:
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data, float(data.get("confidence", 1.0)), str(data.get("rationale", ""))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return {"raw": content}, 1.0, ""


class AgentExecutor(AgentProviderPort):
    def __init__(self, session, *, audit=None) -> None:
        self._session = session
        self._audit = audit
        self._kb = AgentKbProvider(session)

    async def retrieve(self, agent_id, query, *, tenant_id, department_id, top_k=5):
        return await self._kb.retrieve(agent_id, query, tenant_id=tenant_id,
                                       department_id=department_id, top_k=top_k)

    async def execute_task(self, agent_id, task_payload, *, tenant_id, department_id):
        agent = get_agent(self._session, agent_id)
        query = task_payload.get("task", {}).get("summary", "") or str(task_payload.get("input", ""))
        passages = await self._kb.retrieve(agent_id, query, tenant_id=tenant_id,
                                           department_id=department_id)
        completion = invoke_agent_model(agent, _build_prompt(task_payload, passages), audit=self._audit)
        output, confidence, rationale = _parse_output(completion.content)
        tool_calls = self._run_required_tool(agent_id, task_payload, tenant_id, department_id)
        return TaskExecutionResult(
            output=output, confidence=confidence, rationale=rationale, tool_calls=tool_calls,
            kb_citations=[f"{p.document_name}#{p.chunk_reference}" for p in passages],
        )

    def _run_required_tool(self, agent_id, task_payload, tenant_id, department_id):
        tool_name = task_payload.get("criteria", {}).get("must_use_tool")
        if not tool_name:
            return []
        tool = get_tool(self._session, agent_id=agent_id, tool_id=_resolve_tool_id(self._session, agent_id, tool_name))
        out = invoke_tool(self._session, tool, task_payload.get("input", {}),
                          tenant_id=tenant_id, department_id=department_id, audit=self._audit)
        return [{"tool": tool_name, "output": out.output, "success": out.success}]
```

> Helper `_resolve_tool_id(session, agent_id, tool_name)`: query the agent's tools for a matching `display_name`. If Story 2.6's `tool_service` already exposes a by-name lookup, use it; otherwise add a 3-line `list_tools(session, agent_id)` call and match. Keep under the 50-line ceiling by extracting.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/unit/test_agent_executor.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit** (per policy)

```
git add backend/app/modules/agent_builder/agent_executor.py backend/tests/unit/test_agent_executor.py
git commit -m "feat(agent-builder): AgentExecutor runs Agent prompt+model+KB+Tool for a Task"
```

---

## Task 3: Public agent selector `list_routable_agents`

**Files:**
- Modify: `backend/app/modules/agent_builder/service.py`
- Test: `backend/tests/integration/test_orchestrator_decomposition.py` (create; shares this fn)

**Interfaces:**
- Consumes: existing `list_agents(session, *, department_id=None)`.
- Produces: `list_routable_agents(session) -> list[dict]` — each `{"id": str, "name": str, "department_id": str, "system_prompt": str}`. Task 4 consumes it to give the Orchestrator LLM the routing candidates.

- [ ] **Step 1: Write failing test**

```python
# backend/tests/integration/test_orchestrator_decomposition.py
from app.modules.agent_builder.service import list_routable_agents

def test_list_routable_agents_shape(app_session, seeded_agent):
    # tenant context is set by the seeded_agent fixture's tenant (see conftest)
    rows = list_routable_agents(app_session)
    assert isinstance(rows, list)
    if rows:
        assert set(rows[0]) == {"id", "name", "department_id", "system_prompt"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/integration/test_orchestrator_decomposition.py::test_list_routable_agents_shape -v`
Expected: FAIL — `ImportError: cannot import name 'list_routable_agents'`.

- [ ] **Step 3: Implement**

```python
# add to backend/app/modules/agent_builder/service.py
def list_routable_agents(session: Session) -> list[dict]:
    """Public routing candidates for the Orchestrator (AD-1: service, not model access)."""
    return [
        {"id": str(a.id), "name": a.name, "department_id": str(a.department_id),
         "system_prompt": a.system_prompt}
        for a in list_agents(session)
    ]
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/integration/test_orchestrator_decomposition.py::test_list_routable_agents_shape -v`
Expected: PASS (empty or shaped list).

- [ ] **Step 5: Commit** (per policy)

```
git add backend/app/modules/agent_builder/service.py backend/tests/integration/test_orchestrator_decomposition.py
git commit -m "feat(agent-builder): list_routable_agents public selector for orchestrator"
```

---

## Task 4: Orchestrator decomposition — `decompose_run` (Story 3.3)

**Files:**
- Create: `backend/app/modules/orchestrator/schemas.py` (if 3.1 didn't create it)
- Modify: `backend/app/modules/orchestrator/service.py`
- Test: `backend/tests/integration/test_orchestrator_decomposition.py` (extend)

**Interfaces:**
- Consumes: `Workflow`, `WorkflowRun`, `Task` models (3.1/3.2); `list_routable_agents` (Task 3); `LlmPort`; `PostgresAuditSink`; `uuid7`.
- Produces: `TaskSchemaModel` (Pydantic); `decompose_run(session, run_id, *, llm=None, max_tasks=5) -> list[Task]`. Task 6 consumes it via `orchestrate_run`.

**Behavior:** load run + its Workflow; call orchestrator LLM with the description + constraints + routing candidates; parse a JSON array of tasks; validate each against `TaskSchemaModel`; drop invalid → `audit(type="task.dropped_invalid")`; reject `target_agent_id` not in candidates or wrong department → `audit(type="task.routing_rejected")`; cap to `max_tasks`; INSERT surviving Tasks (`status="pending"`); `audit(type="orchestrator.decomposed", input={request, workflow_description}, output={task_ids, routing_rationale})`.

- [ ] **Step 1: Write failing test** (LLM injected — deterministic)

```python
# extend test_orchestrator_decomposition.py
import json, uuid
from app.core.ports.llm import CompletionResult

class FakeLlm:
    def __init__(self, payload): self._p = payload
    def complete(self, messages, model, parameters=None):
        return CompletionResult(content=json.dumps(self._p), model="fake", latency_ms=1)

def test_decompose_inserts_valid_rejects_unknown(app_session, seeded_run_with_two_agents):
    from app.modules.orchestrator.service import decompose_run
    run, agent_a_id, _agent_b_id = seeded_run_with_two_agents
    payload = [
        {"task": {"summary": "screen credit"}, "target_agent_id": str(agent_a_id),
         "input": {"x": 1}, "output": {"type": "object"}, "expected": ["do it"], "criteria": {}},
        {"task": {"summary": "bogus"}, "target_agent_id": str(uuid.uuid4()),  # unknown -> rejected
         "input": {}, "output": {}, "expected": [], "criteria": {}},
    ]
    tasks = decompose_run(app_session, run.id, llm=FakeLlm(payload))
    assert len(tasks) == 1
    assert str(tasks[0].target_agent_id) == str(agent_a_id)
    assert tasks[0].status == "pending"
```

> Fixture `seeded_run_with_two_agents` (add to test file or conftest): seed 2 agents in the run's tenant/department via `AdminSessionLocal`, a Workflow, and a `WorkflowRun` in `running`; set tenant context; yield `(run, agent_a_id, agent_b_id)`. Mirror the `seeded_agent` fixture pattern.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/integration/test_orchestrator_decomposition.py::test_decompose_inserts_valid_rejects_unknown -v`
Expected: FAIL — `decompose_run` missing.

- [ ] **Step 3: Implement Task Schema validator + `decompose_run`**

```python
# backend/app/modules/orchestrator/schemas.py
from typing import Any
from pydantic import BaseModel, Field

class TaskSchemaModel(BaseModel):
    task: dict[str, Any]
    target_agent_id: str
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    expected: list[Any] = Field(default_factory=list)
    criteria: dict[str, Any] = Field(default_factory=dict)
```

```python
# add to backend/app/modules/orchestrator/service.py
import json
from app.core.ids import uuid7, utcnow_iso_ms
from app.core.ports.audit import AuditEntry
from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.adapters.registry import select_llm_adapter
from app.core.ports.llm import Message, ModelRef
from app.modules.agent_builder.service import list_routable_agents
from app.modules.orchestrator.models import Task, WorkflowRun, Workflow
from app.modules.orchestrator.schemas import TaskSchemaModel

# TODO(settings): move to config. Cheap model for dev; swap to premium for demo run.
ORCHESTRATOR_MODEL = ModelRef(provider="anthropic", model_name="claude-haiku-4-5-20251001")

def _orchestrator_llm():
    return select_llm_adapter(ORCHESTRATOR_MODEL.provider)

def _decomposition_prompt(workflow, candidates: list[dict]) -> list[Message]:
    roster = "\n".join(f"- {c['id']} | {c['name']} | dept={c['department_id']}" for c in candidates)
    sys = ("You are a banking Workflow Orchestrator. Decompose the request into <=5 Tasks. "
           "Return ONLY a JSON array; each item = "
           "{task:{summary}, target_agent_id, input, output, expected:[...], criteria:{}}. "
           "target_agent_id MUST be one of the agent ids below.")
    usr = f"REQUEST: {workflow.description}\nCONSTRAINTS: {workflow.constraints}\nAGENTS:\n{roster}"
    return [Message(role="system", content=sys), Message(role="user", content=usr)]

def _audit(session, entry_kwargs):
    PostgresAuditSink(session).log(AuditEntry(ts=utcnow_iso_ms(), **entry_kwargs))

def decompose_run(session, run_id, *, llm=None, max_tasks=5) -> list[Task]:
    run = session.get(WorkflowRun, run_id)
    workflow = session.get(Workflow, run.workflow_id)
    candidates = list_routable_agents(session)
    valid_ids = {c["id"]: c for c in candidates}
    llm = llm or _orchestrator_llm()
    completion = llm.complete(_decomposition_prompt(workflow, candidates), ORCHESTRATOR_MODEL,
                              {"temperature": 0.3})
    raw = _safe_json_array(completion.content)
    tasks: list[Task] = []
    for item in raw[:max_tasks]:
        try:
            ts = TaskSchemaModel(**item)
        except (TypeError, ValueError):
            _audit(session, dict(run_id=str(run_id), step_id=str(uuid7()), agent_id="orchestrator",
                                 type="task.dropped_invalid", input={"item": item}, output={}, latency_ms=0))
            continue
        if ts.target_agent_id not in valid_ids:
            _audit(session, dict(run_id=str(run_id), step_id=str(uuid7()), agent_id="orchestrator",
                                 type="task.routing_rejected", input={"target": ts.target_agent_id},
                                 output={}, latency_ms=0))
            continue
        tasks.append(Task(id=uuid7(), tenant_id=run.tenant_id, run_id=run.id,
                          target_agent_id=ts.target_agent_id, status="pending",
                          schema_payload=ts.model_dump()))
    session.add_all(tasks); session.commit()
    _audit(session, dict(run_id=str(run_id), step_id=str(uuid7()), agent_id="orchestrator",
                         type="orchestrator.decomposed",
                         input={"request": workflow.description, "workflow_description": workflow.description},
                         output={"task_ids": [str(t.id) for t in tasks]}, latency_ms=completion.latency_ms,
                         model=completion.model))
    return tasks

def _safe_json_array(content: str) -> list:
    try:
        data = json.loads(content)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/integration/test_orchestrator_decomposition.py -v`
Expected: all pass (routing rejection audited, 1 Task inserted).

- [ ] **Step 5: Commit** (per policy)

```
git add backend/app/modules/orchestrator/schemas.py backend/app/modules/orchestrator/service.py backend/tests/integration/test_orchestrator_decomposition.py
git commit -m "feat(orchestrator): LLM decomposition into schema-valid routed Tasks (Story 3.3)"
```

---

## Task 5: Task execution with CAS claim — `execute_task_row` (Story 3.4a)

**Files:**
- Modify: `backend/app/modules/orchestrator/service.py`
- Test: `backend/tests/integration/test_orchestrator_execution.py` (create)

**Interfaces:**
- Consumes: `transition_task_status` (3.2 CAS helper); `AgentExecutor` (Task 2); `Task` model; audit helper.
- Produces: `async execute_task_row(session, task, *, executor=None, timeout_s=60, retries=2) -> None` — CAS `pending→claimed`, run `AgentExecutor.execute_task` (with timeout + exp-backoff retry), write `task.result`, CAS `claimed→completed|failed`, audit `task.executed`/`task.failed`.

- [ ] **Step 1: Write failing test**

```python
# backend/tests/integration/test_orchestrator_execution.py
import pytest, uuid
from app.core.ports.agent_provider import TaskExecutionResult

class FakeExecutor:
    def __init__(self, res): self._res = res
    async def execute_task(self, agent_id, payload, *, tenant_id, department_id):
        return self._res

@pytest.mark.asyncio
async def test_execute_task_row_completes(app_session, seeded_pending_task):
    from app.modules.orchestrator.service import execute_task_row
    task = seeded_pending_task
    ex = FakeExecutor(TaskExecutionResult(output={"verdict": "pass"}, confidence=0.8))
    await execute_task_row(app_session, task, executor=ex)
    app_session.refresh(task)
    assert task.status == "completed"
    assert task.result["output"]["verdict"] == "pass"
```

> Fixture `seeded_pending_task`: reuse `seeded_run_with_two_agents`, insert one `Task(status="pending", target_agent_id=agent_a_id, schema_payload={...})`, set tenant context, yield the task.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/integration/test_orchestrator_execution.py::test_execute_task_row_completes -v`
Expected: FAIL — `execute_task_row` missing.

- [ ] **Step 3: Implement**

```python
# add to backend/app/modules/orchestrator/service.py
import asyncio
from app.modules.agent_builder.agent_executor import AgentExecutor
from app.modules.orchestrator.state import transition_task_status  # 3.2 helper location

async def execute_task_row(session, task, *, executor=None, timeout_s=60, retries=2) -> None:
    if not transition_task_status(session, task.id, from_status="pending", to_status="claimed"):
        return  # lost race / not pending (AD-6)
    executor = executor or AgentExecutor(session)
    dept_id = _task_department(session, task)  # read agent dept via agent_builder public service
    try:
        res = await _run_with_retry(executor, task, dept_id, timeout_s, retries)
        transition_task_status(session, task.id, from_status="claimed", to_status="completed",
                               extra_cols={"result": res.model_dump()})
        _audit(session, dict(run_id=str(task.run_id), step_id=str(uuid7()),
                             agent_id=str(task.target_agent_id), type="task.executed",
                             input=task.schema_payload, output=res.model_dump(), latency_ms=0))
    except Exception as exc:  # noqa: BLE001 - record failure, do not swallow audit
        transition_task_status(session, task.id, from_status="claimed", to_status="failed",
                               extra_cols={"result": {"error": str(exc)}})
        _audit(session, dict(run_id=str(task.run_id), step_id=str(uuid7()),
                             agent_id=str(task.target_agent_id), type="task.failed",
                             input=task.schema_payload, output={"error": str(exc)}, latency_ms=0))

async def _run_with_retry(executor, task, dept_id, timeout_s, retries):
    delay = 2
    for attempt in range(retries + 1):
        try:
            return await asyncio.wait_for(
                executor.execute_task(task.target_agent_id, task.schema_payload,
                                      tenant_id=task.tenant_id, department_id=dept_id),
                timeout=timeout_s)
        except (asyncio.TimeoutError, Exception):  # noqa: BLE001
            if attempt == retries:
                raise
            await asyncio.sleep(delay); delay *= 4  # 2s, 8s (FR-9)
```

> `_task_department(session, task)`: fetch the target agent's `department_id` via `agent_builder.service.get_agent(session, task.target_agent_id).department_id` (public service call, AD-1-compliant). Keep as a 2-line helper.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/integration/test_orchestrator_execution.py::test_execute_task_row_completes -v`
Expected: PASS (status completed, result stored).

- [ ] **Step 5: Commit** (per policy)

```
git add backend/app/modules/orchestrator/service.py backend/tests/integration/test_orchestrator_execution.py
git commit -m "feat(orchestrator): CAS task claim + execute + retry/timeout (Story 3.4)"
```

---

## Task 6: Aggregation + orchestration entrypoint — `aggregate_run` / `orchestrate_run`

**Files:**
- Modify: `backend/app/modules/orchestrator/service.py`
- Test: `backend/tests/integration/test_orchestrator_execution.py` (extend)

**Interfaces:**
- Consumes: `decompose_run` (Task 4); `execute_task_row` (Task 5); `transition_run_status` (3.2); `Task`/`WorkflowRun` models.
- Produces: `aggregate_run(session, run_id) -> dict`; `async orchestrate_run(session, run_id, *, llm=None, executor=None) -> None` — the single entrypoint the `run_workflow` worker calls after `pending→running`.

**Behavior of `orchestrate_run`:** `decompose_run` → for each Task sequentially `await execute_task_row` → `aggregate_run` merges all task results into `run.result` → CAS `running→completed` (or `running→failed` if zero tasks survived) → `audit(type="orchestrator.aggregated")`.

- [ ] **Step 1: Write failing test**

```python
# extend test_orchestrator_execution.py
import json, pytest
from app.core.ports.llm import CompletionResult
from app.core.ports.agent_provider import TaskExecutionResult

@pytest.mark.asyncio
async def test_orchestrate_run_end_to_end(app_session, seeded_run_with_two_agents):
    from app.modules.orchestrator.service import orchestrate_run
    run, a_id, b_id = seeded_run_with_two_agents
    payload = [{"task": {"summary": f"t{i}"}, "target_agent_id": str(aid), "input": {},
                "output": {}, "expected": [], "criteria": {}} for i, aid in enumerate([a_id, b_id])]
    class FakeLlm:
        def complete(self, m, model, parameters=None):
            return CompletionResult(content=json.dumps(payload), model="fake", latency_ms=1)
    class FakeExec:
        async def execute_task(self, aid, p, *, tenant_id, department_id):
            return TaskExecutionResult(output={"ok": True}, confidence=0.9)
    await orchestrate_run(app_session, run.id, llm=FakeLlm(), executor=FakeExec())
    app_session.refresh(run)
    assert run.status == "completed"
    assert len(run.result["tasks"]) == 2
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/integration/test_orchestrator_execution.py::test_orchestrate_run_end_to_end -v`
Expected: FAIL — `orchestrate_run` missing.

- [ ] **Step 3: Implement**

```python
# add to backend/app/modules/orchestrator/service.py
from sqlalchemy import select

def aggregate_run(session, run_id) -> dict:
    rows = session.execute(select(Task).where(Task.run_id == run_id)).scalars().all()
    return {"tasks": [{"task_id": str(t.id), "target_agent_id": str(t.target_agent_id),
                       "status": t.status, "result": t.result} for t in rows]}

async def orchestrate_run(session, run_id, *, llm=None, executor=None) -> None:
    tasks = decompose_run(session, run_id, llm=llm)
    if not tasks:
        transition_run_status(session, run_id, from_status="running", to_status="failed")
        return
    for task in tasks:
        await execute_task_row(session, task, executor=executor)
    result = aggregate_run(session, run_id)
    transition_run_status(session, run_id, from_status="running", to_status="completed",
                          )  # NOTE: if 3.2's transition_run_status supports extra result col, pass it; else UPDATE result separately
    session.execute(WorkflowRun.__table__.update().where(WorkflowRun.id == run_id).values(result=result))
    session.commit()
    _audit(session, dict(run_id=str(run_id), step_id=str(uuid7()), agent_id="orchestrator",
                         type="orchestrator.aggregated", input={}, output=result, latency_ms=0))
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/integration/test_orchestrator_execution.py -v`
Expected: all pass; run completed with 2 aggregated task results.

- [ ] **Step 5: Commit** (per policy)

```
git add backend/app/modules/orchestrator/service.py backend/tests/integration/test_orchestrator_execution.py
git commit -m "feat(orchestrator): aggregate tasks + orchestrate_run entrypoint (Story 3.4)"
```

---

## Task 7: Wire `orchestrate_run` into the `run_workflow` worker

**Files:**
- Modify: the `run_workflow` worker body (`backend/app/modules/orchestrator/jobs.py` per 3.2) 
- Test: `backend/tests/integration/test_orchestrator_execution.py` (extend — call worker body with injected fakes)

**Interfaces:**
- Consumes: `run_workflow(ctx, ...)` shell (3.2) + `orchestrate_run` (Task 6).
- Produces: worker that, after CAS `pending→running`, awaits `orchestrate_run(ctx["session"], run_id)`.

- [ ] **Step 1: Write failing test** — assert the worker body invokes orchestration and lands the run `completed`. (Construct a fake `ctx={"session": app_session}`, seed a `pending` run, monkeypatch `orchestrate_run` to a spy, call the worker body, assert spy called with the run id.)

```python
@pytest.mark.asyncio
async def test_run_workflow_calls_orchestrate(app_session, seeded_pending_run, monkeypatch):
    from app.modules.orchestrator import jobs as jobmod
    called = {}
    async def spy(session, run_id, **k): called["run_id"] = run_id
    monkeypatch.setattr(jobmod, "orchestrate_run", spy)
    await jobmod._run_workflow_body(app_session, seeded_pending_run.id)  # extract body for testability
    assert called["run_id"] == seeded_pending_run.id
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/integration/test_orchestrator_execution.py::test_run_workflow_calls_orchestrate -v`
Expected: FAIL — `_run_workflow_body` / wiring missing.

- [ ] **Step 3: Implement** — extract the orchestration call into a testable `_run_workflow_body`:

```python
# in backend/app/modules/orchestrator/jobs.py (3.2 owns the @tenant_aware_job shell)
from app.modules.orchestrator.service import orchestrate_run
from app.modules.orchestrator.state import transition_run_status

async def _run_workflow_body(session, run_id) -> None:
    if not transition_run_status(session, run_id, from_status="pending", to_status="running"):
        return  # already claimed/resumed (AD-6)
    await orchestrate_run(session, run_id)

@tenant_aware_job
async def run_workflow(ctx, *, run_id: str) -> None:
    await _run_workflow_body(ctx["session"], uuid.UUID(run_id))
```

> If Story 3.2 already put the `pending→running` transition in the worker shell, keep it there and have `_run_workflow_body` only call `orchestrate_run` — do not double-transition. Reconcile with 3.2's landed code.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/integration/test_orchestrator_execution.py -v`
Expected: all pass.

- [ ] **Step 5: Full-suite regression + lint (subagent)**

Run: `uv run pytest -q` then `uv run ruff check app tests`
Expected: green (pre-existing arq baseline failures noted in progress.md excepted).

- [ ] **Step 6: Commit** (per policy)

```
git add backend/app/modules/orchestrator/jobs.py backend/tests/integration/test_orchestrator_execution.py
git commit -m "feat(orchestrator): wire orchestrate_run into run_workflow worker"
```

---

## Task 8: Frontend Run views (OUTLINE — expand at execution)

> Per user scope: full detail deferred; this is the shell needed to observe the demo. Two pages, react-router (matches `App.tsx`). No new libs.

- **`/workflows/:id/runs` (`workflow-runs.tsx`):** TanStack Query `GET /workflows/:id/runs` (list from 3.2). Columns: Run id, status pill (map 6 statuses → color), started_at, duration. 1s poll for `running`. Row → detail. Empty state.
- **`/workflows/:id/runs/:runId` (`workflow-run-detail.tsx`):** header (id, status pill, duration); Task Stream from `GET /workflows/:id/runs/:runId` (tasks + statuses), 1s poll while `running`; each task card expands to show `schema_payload` + `result`. Final aggregated `result` panel with a stubbed "View in Trace Dashboard" link (Epic 6). This page is the observable surface for rubric bars 1–3; the Trace Dashboard (Epic 6) renders the audit stream for bar 4.
- Tests: Vitest render smoke + status-pill mapping unit test. Expand to full ACs when Story 3.7/3.8 artifacts are authored.

---

## Self-Review notes

- **Spec coverage:** FR-8 (decompose+validate+route+audit) → Task 4. FR-9 (dispatch, retry×2 exp-backoff 2s/8s, 60s timeout, aggregation audit) → Tasks 5–6. FR-3 real tool use during execution → Task 2 `_run_required_tool`. Bars 1–3 observable → Task 8. Audit graduation (real run_id/step_id) → Tasks 4–7 `_audit`.
- **Consumed-but-external (must exist from 3.1/3.2):** `Workflow/WorkflowRun/Task` models, `transition_run_status`, `transition_task_status` (import path `app.modules.orchestrator.state` — verify actual location in 3.2's landed code and fix imports), `run_workflow` `@tenant_aware_job` shell, arq pool wiring. These are HARD-GATE prereqs, not this plan's tasks.
- **Type consistency:** `TaskExecutionResult` fields identical across Tasks 1/2/5/6. `_audit(session, dict(...))` signature identical everywhere. `execute_task(agent_id, task_payload, *, tenant_id, department_id)` identical in Protocol (T1), adapter (T2), callers (T5).

## Open Questions (carry to execution)

1. `transition_task_status` `extra_cols` param + `transition_run_status` result-column support — confirm exact signatures from 3.2's landed code; adjust Tasks 5–6 if the helper writes `result` differently.
2. `run_workflow` signature: this plan assumes the `@tenant_aware_job` + `enqueue_job_with_context` idiom (reads tenant from decorator). If 3.2 shipped the spec-literal `(ctx, *, run_id, tenant_id)` form, reconcile Task 7's wiring.
3. Orchestrator model choice (`ORCHESTRATOR_MODEL`) — hardcoded Haiku for dev; confirm the demo-run model + move to settings.
4. Tool-by-name resolution (`_resolve_tool_id`) — confirm whether Story 2.6 `tool_service` already exposes a name lookup; reuse if so.
