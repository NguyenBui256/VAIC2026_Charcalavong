# Project Changelog

All notable changes to VAIC. Local commits on branch `rebuild`.

## [Unreleased] — 2026-07-18 (Sub-project A: shared Tools + KB re-platform, backend)

### Changed — Tools & Knowledge Base become tenant-wide shared resources

Backend domain re-platform (spec `docs/superpowers/specs/2026-07-18-shared-tools-kb-re-platform-design.md`,
plan `docs/superpowers/plans/2026-07-18-shared-tools-kb-re-platform.md`). Built subagent-driven
(fresh implementer + spec/quality reviewer per task); ledger `.superpowers/sdd/progress.md`
(Sub-project A section). Commits `0c5a21d`..`23a9ee6` on `rebuild`. Frontend (new sidebar +
Tools/Database sections + agent reference-picker tabs) is handled by a separate concurrent effort
and is **not** part of these commits.

- **Tools are no longer agent-owned.** The `tools` table is now a **tenant-wide catalog** of
  built-in connectors (`tool_type ∈ {rag, gmail, calendar}`, seeded per tenant) carrying a required
  `description` + `params_schema` (the LLM call interface). Agents reference tools via the new M2M
  `agent_tools`. No user-authored tools yet; `gmail`/`calendar` execution is stubbed via the MCP
  stub (like `rag.*`). Removed `Tool.agent_id`/`embedded_python`/`integration_id`/`header`/
  `input_schema` and deleted `tool_crud.py`.
- **KB documents are a tenant-wide store with a user ACL.** `kb_documents` drops `agent_id`, gains
  `owner_id` (uploader = implicit manager) and a nullable `department_id` (optional tag). New
  `kb_document_grants` (per-user `viewer`/`manager` grants) and `agent_kb_documents` (which docs an
  agent may RAG over). Access is enforced in the service layer (`kb_grants_service`); tenant
  isolation stays DB RLS.
- **Two-gate KB retrieval** (`kb_retrieval.kb_search`): an agent gets KB context only if it (a)
  references the `rag` tool AND (b) has granted docs; `rag.search` is scoped to exactly those
  document ids, derived from `agent_kb_documents` — never caller-supplied.
- **APIs**: tenant-wide `GET /tools`, `GET /tools/{id}`; `POST/GET/DELETE /kb/documents` +
  `.../grants`; agent references `GET/POST/DELETE /agents/{id}/tools` and
  `/agents/{id}/kb-documents`. Old nested tool/KB authoring routes removed.
- **Migrations** (greenfield reset, demo-only data): `a1b2c3d4e5f6` (tools catalog + `agent_tools`),
  `b2c3d4e5f6a7` (KB store + `kb_document_grants` + `agent_kb_documents`). Chain onto `c4f1a9d3e7b2`.
- **Demo seed** reshaped: `seed_default_tools` per tenant, KB docs seeded into the store, 3 demo
  agents reference `['rag']` + one granted doc each.

## [Unreleased] — 2026-07-18 (Epic 4: Mini-App Builder + Sandbox)

### Added — Epic 4: Mini-App Builder & Visibility Tier Enforcement (PRD §4.3, FR-12..FR-16)

Demo vertical slice (stories 4-1,2,3,4,5,7) + a build/runtime **sandbox** layer. Commits
`def653e`..`e22ef6e` on `rebuild`. Built subagent-driven (fresh implementer + spec/quality
reviewer per task); spec `docs/superpowers/specs/2026-07-18-mini-app-builder-design.md`, plan
`docs/superpowers/plans/2026-07-18-mini-app-builder.md`, ledger `.superpowers/sdd/progress.md`.

- **Backend `mini_app` module**: from a description, `emission.py` has an LLM emit a
  `{entity_schema, ui_spec}`; `schema_validation.py` validates it against the meta-schema (field
  types `string/longtext/integer/number/boolean/date/enum` + validations); the **pure**
  `provisioner.py` (AD-8) builds a `ProvisioningPlan`; `lifecycle.py`/`service.py` insert a
  `mini_apps` row and enqueue the build. `service.py` is the **sole writer** to `mini_app_rows`
  with **CAS on `updated_at`** → 409 (Divergence-3). Generic visibility-gated CRUD in `routes.py`
  (`/mini-apps` catalog + `/apps/{app_id}/rows*`). `visibility.py` enforces the tier
  (`public`/`need_auth`/`private` + whitelist) at the app layer; tenant isolation is DB RLS.
  Migration `c4f1a9d3e7b2` (`mini_apps` + `mini_app_rows`, RLS ENABLE+FORCE, four access fields
  NOT NULL, FR-13).
- **Sandbox (the "generated app can't affect the platform" guarantee)** — three planes:
  - *Data plane*: declarative-only backend (no per-app server code) + RLS + app-layer tier ⇒ a
    Mini-App can't reach platform tables.
  - *Build plane*: `source_guard.py` (AST/lexical allowlist — only `react`+`./sdk` imports, bans
    `eval`/`window.parent`/`fetch`/…) → pure `codegen.py` (`.tsx`) → `core/ports/build.py`
    `BuildPort` + `core/adapters/esbuild_build.py` run esbuild in an **isolated, resource-capped**
    workdir; the adapter **never raises into the worker** and UUID-validates `app_id` as a path
    component. `mini_app_worker.py` (arq `@tenant_aware_job`) drives
    `pending→building→ready|failed`.
  - *Runtime plane*: bundle served at `/mini-app-runtime/{app_id}` and embedded in a
    `sandbox="allow-scripts allow-forms"` iframe (**no `allow-same-origin`**). The iframe holds a
    **per-app scoped JWT** (`scoped_token.py`, custom `miniapp_id` claim — not reserved `aud`)
    that is **globally denied on every route except its own `/apps/{id}/rows*`** (enforced in
    `AuthMiddleware`), so leaking it into the iframe can't touch the platform. A scoped
    null-origin CORS middleware (`core/miniapp_cors.py`) lets the opaque-origin iframe reach the
    data plane (safe: bearer-token auth, not cookies).
- **Frontend**: `/mini-apps` catalog (`routes/mini-apps.tsx` — list + create form + build-status
  pills), `/mini-apps/:appId` host (`routes/mini-app-host.tsx` — sandboxed iframe + scoped token
  via URL hash), `lib/miniAppsApi.ts`. Replaces the old `/mini-apps` `ComingSoon` stub.
- **Rubric**: delivers **SM-5** (a live Mini-App with real JSONB storage, CRUD, and an
  auth-gated UI). App-Event emission (FR-17, `_emit_row_change` no-op seam) + live event stream
  (4-8) are deferred to the Epic 5 pairing.
- **Verification**: live curl end-to-end for CRUD, a real ~1.1 MB React bundle built + served
  over HTTP, and the scoped-token boundary (403 on `/agents`, `/mini-apps`, cross-app, mint). A
  final whole-branch review caught a browser-only CORS gap (opaque-origin iframe) — fixed. **Not**
  yet browser-smoke-tested; no live LLM key in this env, so emission *quality* is unverified.
- **Known follow-ups (non-blocking)**: LLM infra failures surface as generic 500 (not 422/503);
  `/mini-app-runtime/*` is public, exposing a private-tier app's schema *field names* to a holder
  of its (unguessable UUIDv7) `app_id` — no row data leaks; minor dead-code/unused-param/provenance
  nits. See ledger.

## [Unreleased] — 2026-07-18 (Epic 6 merge)

### Added — Epic 6: Trace Dashboard & Audit Provenance (PRD §4.5, FR-22/23/24)

Merged into `rebuild` via `--no-ff` merge commit `63f009e` (branch `feat/epic6-trace-epic7-seed`).

- **Backend**: `backend/app/modules/audit/service.py` + `routes.py` build out the previously
  1-line-stub audit module into a read/query API over the `audit_trail` table — the same table
  Epic 3's orchestrator writes to with real `run_id`/`step_id` (AD-4). `list_audit_entries`
  (filter by `run_id`/`type`, RLS-scoped, cap 500) and `export_audit_entries` /
  `entries_to_csv` (JSON/CSV export, FR-24) exposed via `GET /audit` and `GET /audit/export`.
- **Frontend**: `/audit` route (`frontend/src/routes/audit.tsx` → `AuditPage`, replacing the old
  `ComingSoon` stub) with `TraceTimeline.tsx` (FR-22 timeline view), `CollaborationGraph.tsx`
  (FR-23 collaboration graph, SVG), `TraceEntryCard.tsx`; hooks/lib `useAuditTrail.ts`,
  `auditApi.ts`, `auditEntryMeta.ts`, `collaborationGraph.ts`. JSON/CSV export wired to the export
  endpoint (FR-24).
- **Rubric coverage**: completes SHB rubric bar 4 (Trace Dashboard) — reading the same
  `audit_trail` that Epic 3 (bars 1–3: specialist collaboration, planner decomposition, real tool
  use) produces. **All 4 rubric bars are now covered end-to-end.**
- **Merge reconciliation**: the source branch's own Epic 7 demo-seed scripts
  (`demo_seed_agents.py`, `demo_seed_workflow.py`) were discarded in favor of `rebuild`'s already
  tested `bootstrap_demo_agents_workflow.py` / `bootstrap_demo_tenant.py` / `demo_agent_specs.py`.
- **Verified runnable post-merge**: alembic single head, pytest 350 passed / 1 flaky / 8 baseline
  errors (pre-existing `test_arq_tenant_context.py` cross-file isolation smell, unrelated to this
  merge), demo smoke test passes, frontend build OK (`tsc --noEmit` + vite), 293 vitest passed.

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
