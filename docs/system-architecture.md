# System Architecture

VAIC backend is a modular monolith (hexagonal/ports-and-adapters), FastAPI + SQLAlchemy +
Postgres RLS for multi-tenancy, arq (Redis) for background jobs. Frontend: React/TypeScript.

## Module Boundaries (AD-1)

Modules under `backend/app/modules/*` (e.g. `orchestrator`, `agent_builder`) never import each
other's ORM models directly. Cross-module access goes through a module's public `service.py`
functions only. The one sanctioned exception is a DB-level foreign key
(`tasks.target_agent_id → agents.id`). Ports live in `backend/app/core/ports/*` as `Protocol`
interfaces (e.g. `AgentProviderPort`, `LlmPort`, `McpClientPort`) implemented by adapters in each
module.

## Orchestrator (Epic 3)

Thin-slice backend implementation of the Workflow Orchestrator (PRD §4.2, FR-7..FR-11).
Delivers SHB rubric bars 1 (specialist collaboration), 2 (planner decomposition), 3 (real tool
use); bar 4 (Trace Dashboard, Epic 6) consumes the audit trail this module writes.

### Data model

Three tables, all with row-level security (RLS) scoped by `tenant_id`:

| Table | Migration | Purpose |
|---|---|---|
| `workflows` | `1ad51bb8e8cb` | Workflow definitions (Story 3.1) |
| `workflow_runs` | `39dfa51cec0c` | One row per Run of a Workflow; status state machine |
| `tasks` | `39dfa51cec0c` | Decomposed units of work within a Run, routed to a Specialist Agent |

### Flow: decompose → dispatch → aggregate

```
POST /workflows/{id}/runs (role=builder)
        │
        ▼
  create_run (status=pending) ──enqueue──▶ arq: run_workflow(run_id)
                                                    │
                                        [@tenant_aware_job sets
                                         tenant_context + SET LOCAL
                                         app.tenant_id]
                                                    ▼
                                     transition_run_status: pending→running (CAS)
                                                    ▼
                                          orchestrate_run(run_id)
                                                    │
                        ┌───────────────────────────┼───────────────────────────┐
                        ▼                                                       │
                 decompose_run                                                  │
             (LLM → ≤5 Task Schema-valid                                        │
              tasks, routed via                                                 │
              list_routable_agents;                                            │
              idempotent — skips if                                            │
              tasks already exist for run)                                     │
                        │                                                       │
                        ▼                                                       │
        for each task: execute_task_row (CAS pending→claimed)                   │
                        │                                                       │
                        ▼                                                       │
              AgentExecutor.execute_task                                        │
        (runs Agent system prompt + model                                       │
         via LlmPort + KB retrieve + Tool                                       │
         via McpClientPort; 60s timeout,                                        │
         retry x2 exponential backoff)                                          │
                        │                                                       │
                        ▼                                                       │
        transition_task_status: claimed→completed/failed (CAS) ◀────────────────┘
                        │
                        ▼
                 aggregate_run
   (Run = completed only if ≥1 task succeeded, else failed)
                        │
                        ▼
      transition_run_status: running→completed/failed (CAS, atomic result write)
```

Every audit event (`orchestrator.decomposed`, `task.dropped_invalid`,
`task.routing_rejected`, `task.executed`, run/task status changes) is written via
`PostgresAuditSink().log(...)` with real `run_id` + `step_id` (uuid7) — not the earlier
`crud_audit_ids` stopgap.

### Key files

| File | Role |
|---|---|
| `backend/app/modules/orchestrator/service.py` | `decompose_run`, `execute_task_row`, `aggregate_run`, `orchestrate_run` |
| `backend/app/modules/orchestrator/state.py` | CAS helpers: `transition_run_status`, `transition_task_status` |
| `backend/app/workers/orchestrator_worker.py` | arq entrypoint `run_workflow(ctx, *, run_id, resume=False)`, `@tenant_aware_job`, `resume_orphaned_runs` on startup |
| `backend/app/modules/agent_builder/agent_executor.py` | `AgentExecutor(AgentProviderPort)` — concrete Task execution (prompt+model+KB+Tool) |
| `backend/app/core/ports/agent_provider.py` | `AgentProviderPort.execute_task` (extension over pre-existing `retrieve`) |
| `backend/app/modules/agent_builder/service.py` | `list_routable_agents` — public routing-candidate selector consumed by the Orchestrator (AD-1) |

### Architecture invariants

- **AD-1 (module boundary)** — orchestrator never imports `agent_builder` ORM models; only its
  public service functions (`list_routable_agents`) or ports (`AgentProviderPort`).
- **AD-4 (audit)** — `PostgresAuditSink` is the sole writer to `audit_trail`; a write failure
  raises and crashes the Run rather than being silently swallowed.
- **AD-6 (CAS state machine)** — every `workflow_runs.status` / `tasks.status` transition is a
  compare-and-set `UPDATE ... WHERE id=? AND status=?`; the caller checks `rowcount==1`; `0` rows
  means a lost race or wrong prior state and the caller abandons cleanly (never force-proceeds).
- **AD-10 (tenant identity across arq)** — job kwargs materialize `tenant_id`; the
  `@tenant_aware_job` decorator sets `tenant_context` + `SET LOCAL app.tenant_id` before the job
  body runs. Because each internal CAS transition does its own commit (which drops session-local
  `SET LOCAL` state in Postgres), the orchestrator calls `_reassert_rls` to re-apply the role +
  tenant GUC after each internal commit within a single job execution.
- **Multi-tenant RLS** — enforced at the Postgres level on `workflows`, `workflow_runs`, `tasks`
  (same pattern as the rest of the platform); RLS only actually isolates tenants when the app
  connects as the non-superuser `vaic_app` role (see project memory: RLS role-config dependency).

### Product decisions (2026-07-18)

- Run status = `failed` when 0 tasks succeed (previously always `completed` regardless of task
  outcomes).
- `POST /workflows/{id}/runs` requires the `builder` role (previously any authenticated tenant
  user could trigger a Run).
- `AgentExecutor` reports `success=False` when a required Tool invocation fails (previously always
  reported `success=True` even on tool failure).

## Epic 7-thin: Demo bootstrap & worker

Seeds a runnable demo without a UI: tenant "SHB Demo", 3 departments (Credit /
Legal-Compliance / Operations), 3 users, 3 Specialist Agents each with one embedded-Python Tool
(`financial-ratio-calculator`, `sanctions-check`, `doc-checklist-verifier`), 1 Workflow
("Business Loan Pre-Screen"). Seed uses real `agent_builder`/`orchestrator` service functions —
no validation bypass — and is idempotent (safe to re-run).

| File | Role |
|---|---|
| `backend/scripts/bootstrap_demo_tenant.py` | Tenant, departments, users |
| `backend/scripts/demo_agent_specs.py` | Agent + Tool spec data |
| `backend/scripts/bootstrap_demo_agents_workflow.py` | Agents, Tools, Workflow (calls real services) |
| `backend/scripts/run_worker.py` | arq worker process entrypoint |

**Start the worker:** `cd backend && uv run python -m scripts.run_worker`

**Demo trigger:** `POST /auth/login` (`admin@shbdemo.vaic` / `Password123!`) → bearer token →
`POST /workflows/{id}/runs`.

**Verification:** `backend/tests/integration/test_demo_smoke.py` drives a real burst `arq.Worker`
end-to-end (decompose → dispatch → aggregate) to a `completed` Run with 3 Tasks, a real tool
sandbox invocation, and all 4 audit event types. Uses a stub LLM for decomposition — no live
Anthropic key is configured in this environment; a live run needs a real key (PRD open question
OQ-2). KB content retrieval is skipped in the smoke test (no embedding provider configured).

## Status & Roadmap

Epic 3 (backend) and Epic 7-thin are complete as of branch `rebuild` head `135b295` (local only,
not pushed). Pending: Epic 6 Trace Dashboard (rubric bar 4 — UI over the `audit_trail` this module
already writes), Task 8 frontend Run views, a live-LLM-key rehearsal run. Deferred: Epic 4
Mini-App, Epic 5 Actions. See `docs/superpowers/specs/2026-07-18-remaining-epics-roadmap-design.md`
for the full roadmap and `.superpowers/sdd/progress.md` for the task-by-task ledger.
