# Codebase Summary

Modular monolith: FastAPI backend (`backend/`) + React/TypeScript frontend (`frontend/`).
Multi-tenant via Postgres RLS. Background jobs via arq (Redis). See
`docs/system-architecture.md` for architecture invariants (AD-1, AD-4, AD-6, AD-10), the
Orchestrator flow, and the Audit/Trace Dashboard (Epic 6) in detail.

`audit_trail` columns: `{id, tenant_id, run_id, step_id, agent_id, ts, type, input, output,
latency_ms, model}` — append-only (INSERT/SELECT only; UPDATE/DELETE revoked).

## Backend module map (`backend/app/modules/*`)

| Module | Status | Purpose |
|---|---|---|
| `agent_builder` | DONE (Epic 2) | Agent CRUD, KB upload/retrieval, Tool config, model catalog, `AgentExecutor` (runs an Agent's prompt+model+KB+Tool for a Task — added Epic 3), `list_routable_agents` public selector for Orchestrator |
| `orchestrator` | DONE, thin-slice (Epic 3) | Workflow CRUD, Run lifecycle (CAS state machine), decomposition (`decompose_run`), dispatch/aggregate (`execute_task_row`, `aggregate_run`, `orchestrate_run`) |
| `tenant` | DONE (Epic 1) | Tenant/department/user foundation, RLS context |
| `audit` | DONE (Epic 6) | Write: `PostgresAuditSink` — sole writer to `audit_trail` (AD-4). Read: `service.list_audit_entries` / `export_audit_entries` / `entries_to_csv`, `routes.py` — `GET /audit`, `GET /audit/export` |
| `mini_app` | Stub, DEFER (Epic 4) | Mini-App Builder — not implemented |
| `actions` | Stub, DEFER (Epic 5) | Actions/Triggers — not implemented |

## Core ports (`backend/app/core/ports/*`)

Protocol interfaces implemented by module adapters (hexagonal architecture, AD-1):

- `agent_provider.py` — `AgentProviderPort` (`retrieve`, `execute_task`), `TaskExecutionResult`
- `llm.py` — `LlmPort`
- `mcp_client.py` — `McpClientPort` (doc intake, tool invocation)
- `tool.py`, `sandbox.py` — Tool execution + embedded-Python sandbox
- `audit.py` — audit sink interface
- `doc_intake.py` — legacy/dead code path superseded by `McpClientPort` (see Epic 2 P4 note in `.superpowers/sdd/progress.md`)

## Background workers (`backend/app/workers/*`)

- `orchestrator_worker.py` — arq entrypoint `run_workflow(ctx, *, run_id, resume=False)`,
  decorated `@tenant_aware_job` (AD-10), registers `resume_orphaned_runs` on startup to recover
  Runs stuck at `running` after a worker crash.

## Demo bootstrap scripts (`backend/scripts/*`, Epic 7-thin)

- `bootstrap_demo_tenant.py` — seeds tenant "SHB Demo", 3 departments, 3 users
- `demo_agent_specs.py` — Agent + Tool spec data (3 Specialist Agents, 1 Tool each)
- `bootstrap_demo_agents_workflow.py` — seeds Agents/Tools/Workflow via real services (idempotent)
- `run_worker.py` — arq worker process entrypoint (`uv run python -m scripts.run_worker`)

## Frontend routes (`frontend/src/routes/*`)

| Route | Status |
|---|---|
| `login`, `dashboard` | DONE |
| `agents`, `agent-builder`, `agent-detail` | DONE (Epic 2) |
| `workflows`, `workflow-detail` | DONE (Epic 3 Story 3.1 — list + Definition tab) |
| `audit` (`AuditPage`) | DONE (Epic 6) — Trace timeline (FR-22), collaboration graph (FR-23), JSON/CSV export (FR-24); deep-link `/audit?run_id=` |
| `orchestrator` | Scaffold |
| `mini-apps.$appId`, `actions` | Stub, DEFER (Epic 4/5) |

### Audit components (`frontend/src/components/audit/*`, Epic 6)

`TraceTimeline.tsx`, `TraceEntryCard.tsx`, `CollaborationGraph.tsx` + `lib/collaborationGraph.ts`,
`hooks/useAuditTrail.ts`, `lib/auditApi.ts`, `lib/auditEntryMeta.ts`. See
`docs/system-architecture.md` → "Audit & Trace Dashboard (Epic 6)" for details.

## Database migrations (Alembic, `backend/alembic/versions/`)

Chain includes (chronological, Epic 3 additions):

- `1ad51bb8e8cb` — `create_workflows_rls` (Story 3.1)
- `39dfa51cec0c` — `create_workflow_runs_tasks_rls` (Story 3.2; `workflow_runs` + `tasks` + RLS)

## Testing

- `backend/tests/integration/test_demo_smoke.py` — end-to-end demo smoke: real arq `Worker`,
  decompose → dispatch → aggregate, real tool sandbox, all 4 audit event types, stub LLM
  (no live Anthropic key in this env).
- Known pre-existing flake: `test_arq_tenant_context.py` cross-file test-isolation smell (8 arq
  errors under full `pytest tests/`; clean per-file). Baseline: 350 passed / 1 flaky / 8 errors.

## References

- `docs/system-architecture.md` — Orchestrator flow, invariants, demo bootstrap
- `docs/project-changelog.md` — dated changelog entries
- `docs/superpowers/specs/2026-07-18-remaining-epics-roadmap-design.md` — roadmap for Epics 3-7
- `.superpowers/sdd/progress.md` — task-by-task execution ledger (source of truth for commit ranges)
