# Project Changelog

All notable changes to VAIC. Local commits on branch `rebuild`, NOT pushed unless noted.

## [Unreleased] — 2026-07-18

### Added — Epic 3: Workflow Orchestrator (PRD §4.2, FR-7..FR-11)

Backend thin-slice, READY-FOR-DEMO. Branch head `135b295`.

- **Story 3.1 — Workflow CRUD + UI**: `workflows` table + RLS (migration `1ad51bb8e8cb`), `/workflows` list page + Definition tab.
- **Story 3.2 — Run lifecycle state machine**: `workflow_runs` + `tasks` tables + RLS (migration `39dfa51cec0c`); compare-and-set (CAS) transitions in `backend/app/modules/orchestrator/state.py` (`transition_run_status`, `transition_task_status`); arq worker `run_workflow` in `backend/app/workers/orchestrator_worker.py` (`@tenant_aware_job`, `resume_orphaned_runs` on startup); arq pool wired into FastAPI app lifespan.
- **Story 3.3 — Decomposition**: `decompose_run` (`backend/app/modules/orchestrator/service.py`) — LLM decomposes a run request into ≤5 schema-valid Tasks (Task Schema, PRD §A1), routes each to a Specialist Agent via `list_routable_agents`, idempotent (skips if tasks already exist for the run), audits `orchestrator.decomposed` / `task.dropped_invalid` / `task.routing_rejected`.
- **Story 3.4 — Dispatch & aggregate**: `execute_task_row` (CAS `pending→claimed→completed/failed`, 60s timeout, retry ×2 exponential backoff), `orchestrate_run` (decompose → sequential execute → aggregate), `AgentExecutor` (`backend/app/modules/agent_builder/agent_executor.py`) runs an Agent's prompt + model + KB + Tool for a Task; `AgentProviderPort.execute_task` extension (`backend/app/core/ports/agent_provider.py`).
- **Product decisions applied**: Run status = `failed` when 0 tasks succeed (was always `completed`); `POST /workflows/{id}/runs` now requires `builder` role; `AgentExecutor` reports `success=False` on tool failure (was always `True`).
- **Architecture invariants enforced**: AD-1 (orchestrator never imports `agent_builder` models, only its public service functions), AD-4 (`PostgresAuditSink` is the sole writer to `audit_trail`, real `run_id`/`step_id`, audit failure crashes the Run rather than being swallowed), AD-6 (CAS on every `workflow_runs.status` / `tasks.status` change), AD-10 (tenant context propagated across arq via `@tenant_aware_job`; `_reassert_rls` re-applies the session role + tenant GUC after each internal commit inside a job body), multi-tenant RLS on all 3 new tables.
- Delivers SHB rubric bars 1 (specialist collaboration — dispatch to ≥2 Agents), 2 (planner decomposition), 3 (real tool use via `AgentExecutor`). Bar 4 (Trace Dashboard, Epic 6) is not yet built; Epic 3 produces the `audit_trail` rows it will read.

### Added — Epic 7-thin: Demo bootstrap (PRD §A6/§A8, FR-28 thin)

Commits up to `135b295`.

- `backend/scripts/bootstrap_demo_tenant.py` (+ `bootstrap_demo_agents_workflow.py`, `demo_agent_specs.py`): idempotent seed of tenant "SHB Demo", 3 departments (Credit / Legal-Compliance / Operations), 3 users, 3 Specialist Agents (Credit Analyst + `financial-ratio-calculator`, Compliance Analyst + `sanctions-check`, Operations Analyst + `doc-checklist-verifier` — all embedded-Python tools), 1 Workflow "Business Loan Pre-Screen". Uses real service functions, no validation bypass.
- `backend/scripts/run_worker.py`: arq worker entrypoint. Start with `cd backend && uv run python -m scripts.run_worker`.
- End-to-end smoke test `backend/tests/integration/test_demo_smoke.py`: a real burst `arq.Worker` drives a Run to `completed`, 3 Tasks, real tool sandbox invocation, all 4 audit event types. Uses a STUB LLM for decomposition (no live Anthropic key configured in this env); a real live run needs an API key (PRD open question OQ-2). KB content retrieval skipped (no embedding provider configured).
- Demo flow: run bootstrap script → start worker → `POST /auth/login` (`admin@shbdemo.vaic` / `Password123!`) → `POST /workflows/{id}/runs`.

### Notes

- Known pre-existing issue (not introduced by this work): `test_arq_tenant_context.py` has a cross-file test-isolation smell causing 8 arq errors under a full `pytest tests/` run (per-file runs are clean). Baseline: 350 passed / 1 flaky / 8 errors.
- Deferred: Epic 6 Trace Dashboard (rubric bar 4), Task 8 frontend run-views, a live-LLM-key run. Out of scope for this cycle: Epic 4 Mini-App, Epic 5 Actions.
- Full task-by-task ledger: `.superpowers/sdd/progress.md`.
