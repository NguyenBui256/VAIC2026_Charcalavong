"""End-to-end demo smoke test (Epic 7 thin-slice).

Proves the FULL plumbing the demo relies on: bootstrap seeds the demo
tenant -> `POST /workflows/{id}/runs` enqueues `run_workflow` -> a REAL
burst `arq.Worker` (mirrors `test_workflow_run_worker_e2e.py`) picks it up
-> `orchestrate_run` decomposes, dispatches to the 3 seeded Specialist
Agents, and aggregates -> the Run reaches a terminal status.

LLM key handling: if `VAIC_ANTHROPIC_API_KEY` is configured, decomposition
AND Agent invocation run against the real Anthropic provider. If not, both
`app.modules.orchestrator.service.select_llm_adapter` and
`app.modules.agent_builder.service.select_llm_adapter` are monkeypatched to
a deterministic stub `LlmPort` so the smoke proves the full plumbing
regardless of a live key -- Tool invocation itself is NEVER stubbed; the
3 seeded Tools run for real inside `SubprocessSandbox`.
"""

from __future__ import annotations

import json

import pytest
from arq import Worker
from arq import func as arq_func
from arq.connections import RedisSettings
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.db import AdminSessionLocal
from app.core.ports.llm import CompletionResult
from app.core.settings import get_settings
from app.core.tenant_context import tenant_context
from app.main import app
from app.modules.agent_builder import service as agent_builder_service
from app.modules.agent_builder.models import Agent
from app.modules.orchestrator import service as orchestrator_service
from app.modules.orchestrator.models import Workflow
from app.workers.orchestrator_worker import run_workflow
from scripts.bootstrap_demo_tenant import DEFAULT_PASSWORD
from scripts.bootstrap_demo_tenant import bootstrap_demo_tenant as _bootstrap

# `_migrations_applied` is provided by tests/integration/conftest.py.

_AUDIT_TYPES_EXPECTED = {
    "orchestrator.decomposed",
    "task.executed",
    "orchestrator.aggregated",
    "workflow_run.transition",
}


class _StubLlm:
    """Deterministic `LlmPort` stand-in for both decomposition + Agent calls.

    Distinguishes the two call sites by the system message content: the
    Orchestrator's decomposition prompt always starts with "You are a
    banking Workflow Orchestrator." (see `orchestrator/service.py`
    `_decomposition_prompt`); every other system message is an Agent's own
    `system_prompt` (`invoke_agent_model`).
    """

    def __init__(self, decomposition_payload: list[dict]) -> None:
        self._decomposition_payload = decomposition_payload

    def complete(self, messages, model, parameters=None) -> CompletionResult:  # noqa: ANN001
        system_content = messages[0].content if messages else ""
        if "Workflow Orchestrator" in system_content:
            content = json.dumps(self._decomposition_payload)
            model_name = "stub-orchestrator"
        else:
            content = json.dumps({"confidence": 0.92, "rationale": "stub demo response"})
            model_name = "stub-agent"
        return CompletionResult(content=content, model=model_name, latency_ms=1)


def _decomposition_payload(agents_by_name: dict[str, Agent]) -> list[dict]:
    """Build the §A6 example decomposition, routed to the seeded Agents."""
    credit = agents_by_name["Credit Analyst"]
    compliance = agents_by_name["Compliance Analyst"]
    ops = agents_by_name["Operations Analyst"]
    return [
        {
            "task": {"summary": "Compute financial ratios and verdict for Acme Trading."},
            "target_agent_id": str(credit.id),
            "input": {
                "financial_summary": {
                    "revenue": 12_000_000_000,
                    "current_assets": 5_000_000_000,
                    "current_liabilities": 3_000_000_000,
                    "ebitda": 2_000_000_000,
                    "debt_service": 1_000_000_000,
                }
            },
            "output": {"type": "object"},
            "expected": ["retrieve policy clauses", "compute ratios", "return verdict"],
            "criteria": {
                "confidence_floor": 0.7,
                "must_cite_kb": True,
                "must_use_tool": "financial-ratio-calculator",
            },
        },
        {
            "task": {"summary": "Run KYC/AML screen on Acme Trading principals."},
            "target_agent_id": str(compliance.id),
            "input": {"principals": ["John Doe", "Jane Smith"]},
            "output": {"type": "object"},
            "expected": ["screen against sanctions list", "return flags"],
            "criteria": {
                "confidence_floor": 0.85,
                "must_cite_kb": True,
                "must_use_tool": "sanctions-check",
            },
        },
        {
            "task": {"summary": "Verify document checklist completeness."},
            "target_agent_id": str(ops.id),
            "input": {
                "required_documents": ["business_license", "financial_statements", "id_proof"],
                "provided_documents": ["business_license", "financial_statements"],
            },
            "output": {"type": "object"},
            "expected": ["read checklist", "match against provided documents"],
            "criteria": {"confidence_floor": 0.9, "must_use_tool": "doc-checklist-verifier"},
        },
    ]


async def test_demo_bootstrap_to_run_completion_smoke(
    _migrations_applied: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    # -- 1. Bootstrap (idempotent) — seeds tenant/depts/users/agents/tools/workflow.
    summary = _bootstrap()
    tenant_id = summary["tenant"].id
    workflow: Workflow = summary["workflow"]

    with AdminSessionLocal() as s:
        agents = list(
            s.execute(select(Agent).where(Agent.tenant_id == tenant_id)).scalars().all()
        )
    agents_by_name = {a.name: a for a in agents}
    assert {"Credit Analyst", "Compliance Analyst", "Operations Analyst"}.issubset(
        agents_by_name
    ), f"expected 3 seeded Agents, got {sorted(agents_by_name)}"

    # -- 2. Determine LLM path: real key vs deterministic stub.
    has_live_key = bool(get_settings().anthropic_api_key)
    if has_live_key:
        llm_path = "real (VAIC_ANTHROPIC_API_KEY configured)"
    else:
        llm_path = "stub (no live provider key — decomposition + Agent calls stubbed)"
        stub = _StubLlm(_decomposition_payload(agents_by_name))
        monkeypatch.setattr(orchestrator_service, "select_llm_adapter", lambda provider: stub)
        monkeypatch.setattr(agent_builder_service, "select_llm_adapter", lambda provider: stub)

    # -- 3. Flush Redis (mirrors test_workflow_run_worker_e2e.py) so no stale jobs.
    import redis.asyncio as aioredis

    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    r = aioredis.from_url(get_settings().redis_url)
    await r.flushdb()
    await r.aclose()

    # -- 4. POST /workflows/{id}/runs as the seeded builder user.
    tenant_context.set(None)
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"email": "admin@shbdemo.vaic", "password": DEFAULT_PASSWORD},
        )
        assert login.status_code == 200, login.text
        token = login.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        run_resp = client.post(
            f"/workflows/{workflow.id}/runs", json={}, headers=headers
        )
        assert run_resp.status_code == 201, run_resp.text
        run_id = run_resp.json()["data"]["id"]
        assert run_resp.json()["data"]["status"] == "pending"
    tenant_context.set(None)

    # -- 5. Drive it through a REAL burst arq.Worker (no stubbing of the worker body).
    worker = Worker(
        functions=[arq_func(run_workflow, name="run_workflow")],
        redis_settings=redis_settings,
        burst=True,
        max_jobs=2,
        job_timeout=90,
        max_tries=1,
    )
    await worker.run_check()

    # -- 6. Assertions.
    try:
        with AdminSessionLocal() as s:
            run_row = s.execute(
                text("SELECT status FROM workflow_runs WHERE id=:id"), {"id": run_id}
            ).fetchone()
            task_rows = s.execute(
                text("SELECT target_agent_id, status, result FROM tasks WHERE run_id=:id"),
                {"id": run_id},
            ).fetchall()
            audit_rows = s.execute(
                text(
                    "SELECT type, agent_id FROM audit_trail WHERE run_id=:id ORDER BY ts"
                ),
                {"id": run_id},
            ).fetchall()

        assert run_row is not None, "Run row missing after worker burst"
        assert run_row[0] in {"completed", "failed"}, (
            f"Run did not reach a terminal state: status={run_row[0]!r}"
        )

        assert len(task_rows) >= 2, f"expected >=2 Tasks, got {len(task_rows)}"
        seeded_agent_ids = {str(a.id) for a in agents}
        assert all(str(t[0]) in seeded_agent_ids for t in task_rows), (
            "a Task routed to an agent outside the seeded 3"
        )

        audit_types = {row[0] for row in audit_rows}
        missing_types = _AUDIT_TYPES_EXPECTED - audit_types
        assert not missing_types, (
            f"audit_trail missing expected step types: {missing_types}; got {audit_types}"
        )

        # >=1 Task actually invoked its Tool for real (`AgentExecutor.
        # _run_required_tool` -> `invoke_tool` -> `SubprocessSandbox`, never
        # stubbed). Checked via `Task.result.tool_calls` rather than
        # `audit_trail` because `tool_service._emit_audit` files tool audit
        # rows under the OQ-1 `crud_audit_ids(tool.id)` stopgap `run_id`
        # (the Tool's own id), NOT the orchestrator Run's id — so they never
        # show up in a `WHERE run_id=<run_id>` audit_trail query.
        tool_calls = [
            call
            for _agent_id, _status, result in task_rows
            for call in (result or {}).get("tool_calls", [])
        ]
        assert tool_calls, "no Task recorded a tool_calls entry in its result"
        assert any(c.get("success") for c in tool_calls), (
            f"no Task's Tool call succeeded: {tool_calls}"
        )

        print(f"[smoke] LLM path: {llm_path}")
        print(f"[smoke] run_id={run_id} final_status={run_row[0]}")
        print(f"[smoke] tasks={len(task_rows)} audit_types={sorted(audit_types)}")
    finally:
        # Cleanup this Run's rows so re-running the smoke test (or the
        # bootstrap idempotency tests) starts from a clean Run slate. The
        # demo tenant/depts/users/agents/tools/workflow are left in place
        # (bootstrap is idempotent by design).
        with AdminSessionLocal() as s:
            s.execute(text("DELETE FROM audit_trail WHERE run_id=:id"), {"id": run_id})
            s.execute(text("DELETE FROM tasks WHERE run_id=:id"), {"id": run_id})
            s.execute(text("DELETE FROM workflow_runs WHERE id=:id"), {"id": run_id})
            s.commit()
