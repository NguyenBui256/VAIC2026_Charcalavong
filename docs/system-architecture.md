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

## Audit & Trace Dashboard (Epic 6)

Read-only query/export surface over the append-only `audit_trail` table (PRD §4.5, FR-22/23/24).
Merged into `rebuild` via `--no-ff` commit `63f009e`. Completes SHB rubric bar 4 — the platform
now covers all 4 rubric bars end-to-end (bars 1–3 from Epic 3, bar 4 from Epic 6), reading the
same `audit_trail` rows the Orchestrator (Epic 3) writes via `PostgresAuditSink` (AD-4).

### Backend (`backend/app/modules/audit`)

| File | Role |
|---|---|
| `service.py` | `list_audit_entries` — RLS-scoped read, filter by `run_id`/`type`, cap 500, ordered by `ts` (ASC per-run / DESC global); `export_audit_entries` + `entries_to_csv` — JSON/CSV export (FR-24), cap 10k rows |
| `routes.py` | `GET /audit?run_id=&type=&limit=` (envelope `{data,error,meta}`); `GET /audit/export?format=json\|csv` (raw file, `Content-Disposition: attachment`) |

The module remains read-only: `PostgresAuditSink` (`backend/app/core/adapters/audit_postgres.py`)
is still the sole writer to `audit_trail` (AD-4). RLS scopes rows to the caller's tenant
automatically — no manual tenant filtering in the read-side Python.

### Frontend (`frontend/src/routes/audit.tsx` → `AuditPage`)

Replaces the previous `ComingSoon` stub. Deep-linkable via `/audit?run_id=` (used from Run views).

| File | Role |
|---|---|
| `components/audit/TraceTimeline.tsx` | FR-22 — vertical timeline, color-coded dot per event type, expand-to-JSON input/output |
| `components/audit/TraceEntryCard.tsx` | Single audit entry card (used by the timeline) |
| `components/audit/CollaborationGraph.tsx` + `lib/collaborationGraph.ts` | FR-23 — SVG graph, Orchestrator → Agent edges weighted by step count; toggle Timeline ⇄ Graph |
| `hooks/useAuditTrail.ts`, `lib/auditApi.ts`, `lib/auditEntryMeta.ts` | TanStack Query hook + API client + event-type→label/color mapping |

`lib/auditApi.ts` exposes `downloadAuditExport` (JSON/CSV) wired to an Export button on the page
(FR-24).

## Mini-App Builder & Sandbox (Epic 4)

Demo vertical slice (PRD §4.3, FR-12..FR-16). From a description an Agent/LLM emits a schema, the
platform provisions a per-app JSONB namespace with auto CRUD, compiles a per-app React UI in an
**isolated build sandbox**, and serves it in a **sandboxed iframe** gated by a per-app scoped
token. Commits `def653e`..`e22ef6e` on `rebuild`. Detail spec:
`docs/superpowers/specs/2026-07-18-mini-app-builder-design.md`.

### Data model (migration `c4f1a9d3e7b2`)

- `mini_apps` — one row per app: `entity_schema`/`ui_spec` (JSONB), `visibility_tier`
  (`public`/`need_auth`/`private`) + `whitelist_user_ids`, `build_status`, `bundle_path`. Unique
  `(tenant_id, slug)`.
- `mini_app_rows` — one row per user record across **all** apps (single-table JSONB namespace,
  FR-13). `tenant_id`/`department_id`/`owner_id`/`data` are NOT NULL. RLS ENABLE+FORCE on both,
  tenant-isolation policy (`app.tenant_id` GUC) — the same pattern as every other table.

### Flow: create → provision → build → serve → open

1. `POST /mini-apps` (role `builder`) with a description (LLM-emitted schema) or a supplied schema
   → `emission.py`/`schema_validation.py` → **pure** `provisioner.py` (AD-8) → `lifecycle.py`
   inserts the row (`build_status=pending`) and enqueues `build_mini_app`. Audited
   (`mini_app.schema_emitted`/`schema_rejected`/`provisioned`) commit-then-audit (AD-4).
2. `mini_app_worker.py` (arq `@tenant_aware_job`): `source_guard.assert_source_safe` →
   `codegen.generate_app_source` → `EsbuildBuild.build` into `mini_app_bundle_root/<app_id>` →
   `build_status=ready|failed`.
3. Row CRUD via the generic `/apps/{app_id}/rows*` router — `service.py` is the **sole writer**
   (Divergence-3), CAS on `updated_at` (409 on conflict). Tier enforced at the app layer
   (`visibility.py`) using the caller's `Principal`; tenant isolation is DB RLS. `_emit_row_change`
   is a no-op seam for FR-17 (Epic 5).
4. Frontend `/mini-apps/:appId` mounts the built bundle in a sandboxed iframe.

### Sandbox model (three planes)

| Plane | Isolation |
|---|---|
| Data | Declarative-only backend (no per-app server code) + RLS + app-layer tier ⇒ no path to platform tables. |
| Build | `source_guard` AST/lexical allowlist (only `react`+`./sdk`; bans `eval`/`window.parent`/`fetch`/…) → pure deterministic `codegen` → `BuildPort`/`EsbuildBuild` runs esbuild in an isolated resource-capped workdir; adapter **never raises into the worker**, UUID-validates `app_id` as a path component. One bad app can only fail its own build. |
| Runtime | Bundle served at `/mini-app-runtime/{id}`; iframe `sandbox="allow-scripts allow-forms"` (no `allow-same-origin` → opaque origin, can't read the parent's token). Per-app scoped JWT (`scoped_token.py`, custom `miniapp_id` claim) is **globally denied** by `AuthMiddleware` on every route but its own `/apps/{id}/rows*`, and can't mint another. `core/miniapp_cors.py` allows the opaque origin's `Origin: null` for the data-plane routes only (safe under bearer-token auth). |

### Key files

Backend: `modules/mini_app/{models,schemas,schema_validation,emission,provisioner,codegen,source_guard,lifecycle,service,visibility,routes,scoped_token,mini_app_worker}.py`,
`modules/mini_app/runtime_template/{index.html,sdk.ts,entry.tsx}`, `core/ports/build.py`,
`core/adapters/esbuild_build.py`, `core/miniapp_cors.py`. Frontend: `routes/mini-apps.tsx`,
`routes/mini-app-host.tsx`, `lib/miniAppsApi.ts`.

### Deferred (Epic 5 pairing)

FR-17 App-Event emission (`_emit_row_change` becomes the Action Bus publish), story 4-8 live event
stream, and orchestrator-triggered mid-Run emission (`service` is already orchestrator-callable).

## Status & Roadmap

Epic 3 (backend), Epic 4 (Mini-App Builder + sandbox, demo slice), Epic 6 (Trace Dashboard), and
Epic 7-thin are complete on branch `rebuild`. All 4 SHB rubric bars are covered end-to-end; Epic 4
adds rubric SM-5 (a live Mini-App with real storage). Remaining: a browser smoke test of the Epic 4
runtime + a live-LLM-key rehearsal run (PRD OQ-2, also gates Mini-App emission *quality*); optional
embedding of trace inside `/workflows/$id/runs/$runId` (reachable via `/audit?run_id=` today).
Deferred: Epic 5 Actions (incl. FR-17 App-Event emission that pairs with the Epic 4 seam). See
`docs/superpowers/specs/2026-07-18-remaining-epics-roadmap-design.md` for the full roadmap and
`.superpowers/sdd/progress.md` for the task-by-task ledger.
