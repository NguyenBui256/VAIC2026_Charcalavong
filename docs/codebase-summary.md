# Codebase Summary

Modular monolith: FastAPI backend (`backend/`) + React/TypeScript frontend (`frontend/`).
Multi-tenant via Postgres RLS. Background jobs via arq (Redis). See
`docs/system-architecture.md` for architecture invariants (AD-1, AD-4, AD-6, AD-10), the
Orchestrator flow, the Audit/Trace Dashboard (Epic 6), and the Mini-App Builder + sandbox
(Epic 4) in detail.

`audit_trail` columns: `{id, tenant_id, run_id, step_id, agent_id, ts, type, input, output,
latency_ms, model}` — append-only (INSERT/SELECT only; UPDATE/DELETE revoked).

## Backend module map (`backend/app/modules/*`)

| Module | Status | Purpose |
|---|---|---|
| `agent_builder` | DONE (Epic 2); re-platformed Sub-project A | Agent CRUD, model catalog, `AgentExecutor`, `list_routable_agents`. **Tools + KB are now tenant-wide shared resources** (Sub-project A): `tools` = built-in catalog (`rag`/`gmail`/`calendar`) referenced via `agent_tools` (M2M); `kb_documents` = tenant store with `owner_id` + `kb_document_grants` (user ACL viewer/manager) + `agent_kb_documents` (per-agent RAG grant). Services: `tool_catalog_service`, `kb_service`, `kb_grants_service`, `agent_kb_service`; routes `tool_routes` (`/tools`), `kb_routes` (`/kb/documents` + grants). KB retrieval is **two-gate** (agent must reference `rag` tool AND have granted docs; `rag.search` scoped to those doc ids). `gmail`/`calendar` execution is MCP-stubbed. |
| `orchestrator` | DONE, thin-slice (Epic 3) | Workflow CRUD, Run lifecycle (CAS state machine), decomposition (`decompose_run`), dispatch/aggregate (`execute_task_row`, `aggregate_run`, `orchestrate_run`) |
| `tenant` | DONE (Epic 1) | Tenant/department/user foundation, RLS context |
| `audit` | DONE (Epic 6) | Write: `PostgresAuditSink` — sole writer to `audit_trail` (AD-4). Read: `service.list_audit_entries` / `export_audit_entries` / `entries_to_csv`, `routes.py` — `GET /audit`, `GET /audit/export` |
| `mini_app` | DONE, demo slice (Epic 4) | Mini-App Builder + sandbox. From a description, LLM emits + validates an entity-schema/UI-spec (`emission.py`, `schema_validation.py`), a pure provisioner (`provisioner.py`, AD-8) creates a `mini_apps` row; `service.py` is the sole writer to `mini_app_rows` (CAS on `updated_at`, Divergence-3); generic visibility-gated CRUD (`routes.py` `/mini-apps` + `/apps/{id}/rows*`); app-layer tier enforcement (`visibility.py`). Sandbox: `source_guard.py` (AST/lexical allowlist) → pure `codegen.py` (`.tsx`) → isolated esbuild build via `mini_app_worker.py` → static serve at `/mini-app-runtime/{id}` → sandboxed iframe + per-app scoped token (`scoped_token.py`). App-Event emission is a no-op seam (`_emit_row_change`), deferred to Epic 5 |
| `actions` | Stub, DEFER (Epic 5) | Actions/Triggers — not implemented |

## Core ports (`backend/app/core/ports/*`)

Protocol interfaces implemented by module adapters (hexagonal architecture, AD-1):

- `agent_provider.py` — `AgentProviderPort` (`retrieve`, `execute_task`), `TaskExecutionResult`
- `llm.py` — `LlmPort`
- `mcp_client.py` — `McpClientPort` (doc intake, tool invocation)
- `tool.py`, `sandbox.py` — Tool execution + embedded-Python sandbox
- `build.py` — `BuildPort` (`build(app_id, tsx_source, out_dir) -> BuildResult`); adapter `core/adapters/esbuild_build.py` bundles a per-app React app in an isolated, resource-capped esbuild step (never raises into the worker; `app_id` UUID-validated as a path component)
- `audit.py` — audit sink interface
- `doc_intake.py` — legacy/dead code path superseded by `McpClientPort` (see Epic 2 P4 note in `.superpowers/sdd/progress.md`)

## Background workers (`backend/app/workers/*`)

- `orchestrator_worker.py` — arq entrypoint `run_workflow(ctx, *, run_id, resume=False)`,
  decorated `@tenant_aware_job` (AD-10), registers `resume_orphaned_runs` on startup to recover
  Runs stuck at `running` after a worker crash.
- `modules/mini_app/mini_app_worker.py` (Epic 4) — arq job `build_mini_app(ctx, *, app_id)`,
  `@tenant_aware_job`; transitions `build_status` `pending→building→ready|failed`, runs
  guard→codegen→esbuild, writes the bundle under `mini_app_bundle_root`. Registered in
  `scripts/run_worker.py` via `dataclasses.replace(worker_config, functions=[…])` so the
  `orchestrator` module is never imported into it (AD-1).

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
| `mini-apps` (`MiniAppsPage`), `mini-app-host` (`MiniAppHostPage`) | DONE (Epic 4) — catalog list+create; `/mini-apps/:appId` mounts the generated app in a `sandbox="allow-scripts allow-forms"` iframe (no `allow-same-origin`) with a per-app scoped token passed via the URL hash. Client: `lib/miniAppsApi.ts` |
| `actions` | Stub, DEFER (Epic 5) |

### Audit components (`frontend/src/components/audit/*`, Epic 6)

`TraceTimeline.tsx`, `TraceEntryCard.tsx`, `CollaborationGraph.tsx` + `lib/collaborationGraph.ts`,
`hooks/useAuditTrail.ts`, `lib/auditApi.ts`, `lib/auditEntryMeta.ts`. See
`docs/system-architecture.md` → "Audit & Trace Dashboard (Epic 6)" for details.

## Database migrations (Alembic, `backend/alembic/versions/`)

Chain includes (chronological, Epic 3 additions):

- `1ad51bb8e8cb` — `create_workflows_rls` (Story 3.1)
- `39dfa51cec0c` — `create_workflow_runs_tasks_rls` (Story 3.2; `workflow_runs` + `tasks` + RLS)
- `c4f1a9d3e7b2` — `create_mini_apps_rls` (Epic 4; `mini_apps` + `mini_app_rows`, tenant RLS ENABLE+FORCE on both; `mini_app_rows` four access fields NOT NULL)
- `a1b2c3d4e5f6` — `reshape_tools_catalog` (Sub-project A; tenant-wide `tools` catalog + `agent_tools` M2M, RLS; greenfield DROP+CREATE of `tools`)
- `b2c3d4e5f6a7` — `reshape_kb_store_grants` (Sub-project A; `kb_documents` store + `owner_id`, `kb_document_grants` user ACL, `agent_kb_documents` M2M, RLS on all three)

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
