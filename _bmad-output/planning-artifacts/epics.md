---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-VAIC-2026-07-17/prd/index.md
  - _bmad-output/planning-artifacts/prds/prd-VAIC-2026-07-17/prd/4-features.md
  - _bmad-output/planning-artifacts/prds/prd-VAIC-2026-07-17/prd/8-constraints-guardrails-nfrs.md
  - _bmad-output/planning-artifacts/architecture/architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/index.md
  - _bmad-output/planning-artifacts/architecture/architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/invariants-rules.md
  - _bmad-output/planning-artifacts/architecture/architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/stack.md
  - _bmad-output/planning-artifacts/architecture/architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/structural-seed.md
  - _bmad-output/planning-artifacts/architecture/architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/closed-loop-the-load-bearing-flow.md
  - _bmad-output/planning-artifacts/architecture/architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/dependency-direction.md
  - _bmad-output/planning-artifacts/architecture/architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/consistency-conventions.md
  - _bmad-output/planning-artifacts/design/design-system.md
  - _bmad-output/planning-artifacts/design/platform-design.md
  - _bmad-output/planning-artifacts/design/README.md
---

# VAIC - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for VAIC, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

**FR-1: Create and persist a Specialist Agent** — User with builder role can create a Specialist Agent by naming it, assigning it to a Department, and writing a system prompt. Persisted as Tenant-scoped record with `created_at`, `owner_id`, version metadata.

**FR-2: Per-Agent Knowledge Base (upload + RAG retrieval)** — User uploads documents (PDF, TXT, Markdown, DOCX) to an Agent's KB. Platform chunks, embeds, indexes, and serves retrieval at runtime. KB access isolated to Agent's Department.

**FR-3: Per-Agent Tool configuration** — User registers Tools on an Agent: display name, header (incl. auth), input/output JSON Schema, optional embedded Python. Tools invocable by Agent during Workflow Run.

**FR-4: Per-Agent API Integration configuration** — User registers reusable API Integrations (stubbed Gmail, Calendar, bank-core endpoints). Named connection referenced by Tools.

**FR-5: Per-Agent Model selection (user-configurable)** — User picks Model for Agent from Model Layer's configured providers (Anthropic, OpenAI, Google, Ollama). Platform never fixes the Model.

**FR-6: Agent ownership and Department scoping** — Every Agent carries `tenant_id`, `department_id`, `owner_id`. Listing returns only same-Tenant Agents; editing requires `owner_id == caller` or builder role in same Department.

**FR-7: Workflow definition (natural-language or structured)** — User creates a Workflow with name + natural-language description + optional constraints. Persisted as Tenant-scoped record. Description is a hint; decomposition is dynamic per request.

**FR-8: Dynamic task decomposition by the Orchestrator** — On Workflow Run, Orchestrator (LLM-driven) reads request, produces Tasks conforming to Task Schema (`task / input / output / expected / criteria`). Each Task routed to exactly one Specialist Agent by Department + capabilities.

**FR-9: MCP-based task dispatch and aggregation** — Platform dispatches each Task via MCP (retry up to 2x with exponential backoff), collects Agent responses, aggregates into single Run result. Timeout = 60s per Agent.

**FR-10: Human-in-the-loop escalation** — On conflict / low confidence / explicit "needs human" flag, Orchestrator pauses Run and surfaces human-review item with status, per-step feedback, decision prompt. User resolves/overrides/rejects; Run resumes. Unresolved escalation after 5 minutes triggers Run-level timeout.

**FR-11: Per-step feedback incorporation** — Specialist Agent attaches structured feedback (`confidence: 0–1`, `flags: enum`, `rationale: text`). Orchestrator consumes feedback to decide aggregate/escalate/follow-up.

**FR-12: Agent-emitted entity schema + UI spec** — Agent (or Orchestrator) emits JSON entity schema (`{fields, types, validations}`) + UI spec (`{layout, components, primary_actions}`). Validates against platform's schema-meta-schema.

**FR-13: Auto-provisioned JSONB Namespace** — On valid schema, platform provisions namespace: rows carry `tenant_id`, `department_id`, `owner_id`, `visibility_tier` + schema-defined fields as JSONB. Unique `app_id` within 2s of emission.

**FR-14: Auto-generated CRUD endpoints** — Each Mini-App gets `POST/GET/LIST/PATCH/DELETE` endpoints generated from entity schema, with Visibility Tier enforced. Endpoints exist within 2s of namespace provisioning.

**FR-15: Auto-generated auth-gated UI** — Each Mini-App gets React UI rendered from UI spec at unique path, gated by same Visibility Tier rules. Reachable within 5s of endpoint generation.

**FR-16: Visibility Tier enforcement** — Platform enforces `Public` / `Need-Auth` / `Private` on every read/write at both API and UI layers. Anonymous → 401; wrong-Department → 403; non-whitelisted same-Department → 403.

**FR-17: App Event emission back into the Action Bus** — Every material change to Mini-App row (create/update/delete) emits structured App Event (`app_id`, `tenant_id`, `department_id`, `actor_user_id`, `event_type`, `payload`, `timestamp`). Visible within 1s; sequence numbers for gap detection.

**FR-18: Schedule Trigger (cron)** — User registers Schedule Trigger that fires Workflow Run on cron schedule (5-field syntax). Fires within 60s of scheduled time. Each firing creates a Run visible in Trace Dashboard.

**FR-19: Event Trigger (on App Event)** — User registers Event Trigger firing Workflow Run on matching App Event. Filter by `app_id`, `event_type`, optional JSON-path predicate. Matching events fire Run within 5s.

**FR-20: Action Bus reliability** — At-least-once delivery of App Events and Schedule Triggers to subscribers, with sequence numbers per `app_id`. Crashed subscriber resumes from last-acked sequence.

**FR-21: Per-step Audit Trail logging** — Every Run step (decomposition, dispatch, retrieval, Tool call, Model invocation with name+prompt+latency, aggregation, escalation, Mini-App emission) logged as append-only Audit Trail entry carrying `{run_id, step_id, agent_id, timestamp, type, input, output, latency_ms, model}`.

**FR-22: Trace Dashboard — timeline view** — Vertical timeline rendering Audit Trail; each step a card with type/agent/latency/expand-for-detail. 20+ step Run renders <1s. Shareable by URL within Tenant.

**FR-23: Trace Dashboard — collaboration graph** — Same Audit Trail rendered as graph: Orchestrator node at top, Specialist Agent nodes below, edges labelled with Task type/status. Renders <1s for Runs with ≤10 Agent invocations.

**FR-24: Audit export** — User exports Run's Audit Trail as JSON, signed with Tenant's audit key. Complete within 5s for Runs ≤1000 entries.

**FR-25: Multi-Tenant data isolation** — Every record carries `tenant_id`. Data layer enforces isolation: no query returns another Tenant's rows, even under direct DB access. Verified via direct SQL inspection.

**FR-26: Model Layer (provider-agnostic)** — Model Layer abstracts LLM providers behind single interface. Agents specify Model via `{provider, model_name, parameters}`. Adding new provider requires no changes to Agent/Orchestrator/Mini-App code.

**FR-27: ReactJS frontend SPA** — Single-page application covering Agent Builder, Workflow Orchestrator (definition + Run view), Mini-App catalog, Trace Dashboard, Action configuration, minimal account/Department switching.

**FR-28: Tenant bootstrapping (demo-ready)** — Bootstrap script creates Tenant with: ≥1 User per role, ≥2 Departments, ≥1 pre-configured Workflow ready to Run. Completes <60s, idempotent, not a hard-coded demo.

### NonFunctional Requirements

**NFR-1 (Performance — Orchestrator):** First-response (request → first Task dispatched) <5s p95 on demo hardware.

**NFR-2 (Performance — Mini-App):** Mini-App page load <2s p95.

**NFR-3 (Performance — Trace Dashboard):** Trace Dashboard render <1s for any Run with ≤1,000 Audit Trail entries.

**NFR-4 (Concurrency):** Platform supports ≥5 simultaneous Workflow Runs for the demo without degradation.

**NFR-5 (Observability — LLM logging):** Every LLM call logs `{provider, model, prompt_token_count, completion_token_count, latency_ms}` to Audit Trail. Platform logs queryable by `run_id`.

**NFR-6 (Security — Tenant isolation):** Per-Tenant isolation enforced at data layer (RLS). API Integrations use stored credentials, never hard-coded secrets in source.

**NFR-7 (Reliability — Resume):** Workflow Runs are resumable after process restart (Run state persisted to PostgreSQL).

**NFR-8 (Reliability — Delivery):** Action Bus delivers App Events at-least-once (FR-20).

**NFR-9 (Banking Data Sensitivity — PII):** Platform must not log raw PII (citizen ID, account number, full name) into Audit Trail unless originating Agent marks entry as PII-safe. KB uploads limited to policy/regulation/SOP docs. Demo Tenant uses synthetic loan cases only.

**NFR-10 (Cost Guardrails):** Model Layer exposes per-Run token spend counter visible in Trace Dashboard. Run exceeding 50,000 tokens emits warning (not aborted).

### Additional Requirements

**AR-1 (Starter Template — Structural Seed):** Greenfield monorepo layout defined by Architecture. Structure to initialize in Epic 1 Story 1:

```
vaic/
  backend/
    app/
      main.py                    # FastAPI app, middleware, route registration
      modules/
        tenant/                  # FR-25, FR-28
        agent_builder/           # FR-1..FR-6
        orchestrator/            # FR-7..FR-11
        mini_app/                # FR-12..FR-17
        actions/                 # FR-18..FR-20
        audit/                   # FR-21..FR-24
      core/
        ports/                   # llm, tool, audit, mcp_client, doc_intake
        adapters/                # anthropic, openai, google, ollama, mcp_client, sandbox
        tenant_context.py        # contextvars + middleware
        errors.py                # error envelope
      bootstrap/
        seed_demo_tenant.py      # FR-28
    tests/{unit,integration,e2e}/
    pyproject.toml
    alembic.ini
  frontend/
    src/
      routes/                    # file-based routing
        agent-builder/
        orchestrator/
        mini-apps.$appId/
        trace.$runId/
        actions/
      components/
      hooks/
      lib/
    vite.config.ts
    package.json
  infra/
    docker-compose.yml           # postgres, redis
```

**AR-2 (Architecture Decision — AD-1):** Hexagonal Modular Monolith. One FastAPI process composed of six bounded modules. Domain logic at module center; HTTP routes, DB, LLM, MCP, sandbox are ports/adapters. Cross-module calls go through public service interfaces.

**AR-3 (Architecture Decision — AD-2):** Multi-tenant isolation via Postgres RLS. Every table carries `tenant_id UUID NOT NULL`. RLS policies enforce `tenant_id = current_setting('app.tenant_id')`. FastAPI middleware sets session variable per request from authenticated user. Application code never filters tenant_id manually. Only bootstrap + migrations run with `BYPASSRLS`.

**AR-4 (Architecture Decision — AD-3):** VAIC is an MCP **client**. Tools owned by parallel-team MCP server invoked via `McpClientPort`. The MCP server itself is OUT OF SCOPE — VAIC does not build/host/own it. Task state lives in `tasks` Postgres table, claimed and completed by orchestrator's worker loop. The PRD's "MCP doubles as Task Store" is RELAXED for MVP.

**AR-5 (Architecture Decision — AD-4):** Single audit sink. `audit.log(entry)` in `core/ports/audit.py` is the only path to write `audit_trail`. Every Run step MUST call it. Table grants INSERT only to app role; UPDATE and DELETE revoked. Append-only enforced at DB. **If `audit.log()` call fails, calling Run transitions to `failed` — never silently drop an entry.**

**AR-6 (Architecture Decision — AD-5):** Visibility Tier enforced at row level on `mini_app_rows` via RLS policies encoding access matrix using `visibility_tier`, `department_id`, whitelist check. No client-side or API-only gating.

**AR-7 (Architecture Decision — AD-6):** Persisted state machines with compare-and-set on every transition. Single `UPDATE ... WHERE id=? AND status=?` with application checking `rowcount == 1`. State machines:
- `workflow_runs.status`: `pending | running | awaiting_human | completed | failed | timed_out`. arq workers poll `pending` on startup and resume. Escalations flip `running → awaiting_human`; 5-min timeout flips `awaiting_human → timed_out`.
- `tasks.status`: `pending | claimed | completed | failed`. Specialist Agent worker claims via `UPDATE ... WHERE status='pending'`.
- `mini_app_rows`: optimistic `version` column bumped on every UPDATE; stale-version write rejected.

**AR-8 (Architecture Decision — AD-7):** `LlmPort` (`complete`, `stream`, `embed`) in `core/ports/llm.py` is the only abstraction agents and orchestrator may import. Adapters: anthropic, openai, google, ollama. Agent record stores `{provider, model_name, parameters}` as data.

**AR-9 (Architecture Decision — AD-8):** Mini-App emission is JSON document validated against schema-meta-schema before persistence. Provisioner is function `(tenant_id, department_id, owner_id, valid_schema, initial_rows?) -> (namespace + CRUD endpoints + UI)`. Creates namespace AND initial rows **atomically in one DB transaction**. After provisioning, `mini_app` module's auto-generated CRUD endpoints are sole writers to `mini_app_rows`. Specialist Agents never write to `mini_app_rows` directly post-provisioning. App Event emission fires from CRUD endpoints.

**AR-10 (Architecture Decision — AD-9):** App Events flow only through Action Bus (arq queue). Event Triggers subscribe via filter expressions. Workflow Runs start only via: (a) explicit user action, (b) Schedule Trigger, (c) Event Trigger match. No direct Mini-App → Workflow Run call paths.

**AR-11 (Architecture Decision — AD-10):** Tenant context materialized in job payloads and re-set at worker entry. `tenant_context` set by FastAPI middleware on HTTP paths. For every background job, enqueuer MUST capture `tenant_id`/`department_id` and serialize into arq job kwargs. Worker function's first action: deserialize, set contextvar, `SET LOCAL app.tenant_id` on DB connection before any domain work. Schedule Triggers fan out per-tenant from single `cron_jobs` entrypoint running under `BYPASSRLS`.

**AR-12 (Architecture Decision — AD-11):** Client-side department scope on every MCP call. Every `McpClientPort` call MUST include `tenant_id` + `department_id`. VAIC enforces client-side that parameters match calling Agent's `department_id`; mismatch raises before network. MCP server trusted to honor scope.

**AR-13 (Stack — pinned versions):**
- Backend: Python 3.13, FastAPI 0.139.x, SQLAlchemy 2.x (sync), Pydantic 2.x, Alembic latest, PostgreSQL 18, pgvector 0.7+ (only if FR-2 reconciliation yields VAIC-side retrieval), Redis 7.4+ (arq broker), arq 0.26+, `mcp` Python SDK v1.x, `anthropic` 0.114.0, `openai` latest, `google-genai` latest (optional).
- Frontend: React 19, Vite 8, TypeScript 7.x, Tailwind CSS 4, TanStack Query latest, Vitest, Playwright.

**AR-14 (Consistency Conventions):**
- Entity IDs: UUID v7 (time-ordered). Never autoincrement.
- Timestamps: UTC ISO 8601 with milliseconds, `timestamptz` column type.
- Tenant context: `contextvars.ContextVar` set by FastAPI middleware; arq workers re-set from materialized payload.
- Error shape: `{error: {code, message, details, trace_id}}` — every API error.
- API envelope: `{data, error, meta}` with pagination in `meta`.
- Event naming: `domain.event_type` (e.g., `mini_app.row.created`).
- Audit entry: `{run_id, step_id, agent_id, ts, type, input, output, latency_ms, model}`.
- File naming: Python `snake_case`; routes `kebab-case`; React components `PascalCase`; CSS `kebab-case`.
- Function size: hard ceiling 50 lines (backend + frontend).
- Async jobs: arq only (no Celery, no APScheduler, no background threads for domain work).
- Embedded Python Tools: subprocess only, no network, restricted builtins, 10s CPU cap, 128MB memory.
- Definition of Done: tests pass with evidence (`file:line` + green run) AND production code reference (`file:line`) visible in PR.
- No premature abstraction: Rule of Three before extracting shared helper or introducing a port.
- Error handling: exceptions in domain code; API boundary translates to envelope. Never swallow. Never return `None` to mean error.

**AR-15 (Reconciled Divergences):** Eight adversarial divergences (D1–D8) reconciled into architecture rules — all reflected in AR-3 through AR-12 above. Key reconciliations: tenant contextvar materialization across arq boundary (AD-10), schedule trigger per-tenant fan-out, mini_app single ownership (mini_app module owns writes), concurrent task claim via compare-and-set (AD-6), MCP department scope enforced client-side (AD-11), audit sink failure crashes Run (AD-4), provisioner atomic transaction (AD-8), orchestrator double-pick prevention via state machine (AD-6).

### UX Design Requirements

**UX-DR1: Design Token System** — Implement complete CSS custom property palette in `frontend/src/styles/tokens.css`: hybrid palette (Indigo = AI/modernity, Slate = banking trust, Emerald = success/resolution) with full light/dark mode support. No hardcoded hex values anywhere — all colors reference tokens.

**UX-DR2: Typography System** — Plus Jakarta Sans for UI (32px→12px scale, 14px base for pro-tool density), JetBrains Mono for technical content (IDs, code, audit entries). Implement responsive type scale with `clamp()` where appropriate.

**UX-DR3: Button Component Primitives** — 5 variants: Primary (bg-primary text-on-primary — Run, Save, Submit), Secondary (bg-surface border — Cancel), Ghost (bg-transparent — toolbar), Destructive (bg-destructive — Delete), Icon (36×36 square, always `aria-label` + tooltip). Min height 36px. Primary CTA is singular per view.

**UX-DR4: Status Pills** — 6 states with locked icon+color mapping: Pending (amber, Clock), Running (sky, Loader-spin), Success (emerald, Check), Error (rose, X), Escalated (amber-600, AlertTriangle), Draft (slate-400, Pencil). Always icon + label.

**UX-DR5: Card Component** — `1px` border `--color-border`, no shadow default. Shadow `sm` only when card is interactive or floating. 16px padding. Title (`h3`) + optional status pill in header row.

**UX-DR6: Table Component** — Sticky header variant for long lists. Header: caption weight 600 uppercase slate-500. Row hover: `bg-surface-muted`. Selected row: `bg-primary-soft` with `border-l-2 border-primary`. Bulk actions: checkbox column + sticky action bar.

**UX-DR7: Code / JSON Block Component** — `bg-surface-inset`, mono-small font, 12px padding, 8px border-radius. Inline copy button top-right. Syntax-highlight via `rehype-highlight` or `shiki` with restrained token colors.

**UX-DR8: Form Patterns** — Labels always visible above input (never placeholder-only). Required fields marked with `*` in destructive color. Helper text below input; error replaces helper text in destructive color. Inline validation on blur, not keystroke.

**UX-DR9: Motion System** — Restrained durations: hover/press 120ms, modal/drawer 200ms, Run status transition 240ms, trace step appears 180ms fade + 4px slide-up, escalation toast 280ms slide-in, page transition 160ms cross-fade. Easing: `cubic-bezier(0.16, 1, 0.3, 1)` for modals, ease-out for feedback. **Mandatory:** `prefers-reduced-motion` freezes all animations; trace updates interruptible; never animate `width/height/top/left` — transform and opacity only.

**UX-DR10: Iconography System** — Lucide (`lucide-react`) primary, 1.5px stroke globally. Locked semantic assignments: Bot=Agent, Workflow=Orchestrator, LayoutGrid/AppWindow=Mini-App, Activity/FileSearch=Trace/Audit, Zap=Actions/Trigger, BookOpen/Library=KB, Wrench=Tool, Plug/Webhook=API Integration, Cpu=Model, Building2=Department, Landmark=Tenant, Play=Run, AlertTriangle=Escalation, Radio=Stream/Live. Never use emojis as structural icons.

**UX-DR11: Authoritative State System** — 5 Run/Task statuses with consistent colors and icons everywhere: `pending` (amber Clock), `running` (sky Loader-spin), `success` (emerald Check), `error` (rose X), `escalated` (amber-600 AlertTriangle). Run aggregates Task statuses: Run = escalated if any Task escalated; else error if any errored; else worst pending/running.

**UX-DR12: Accessibility Commitments** — WCAG AAA contrast ratios (text ≥4.5:1, UI glyphs ≥3:1), independently verified for dark mode. Visible focus ring: `box-shadow: 0 0 0 2px var(--color-bg), 0 0 0 4px var(--color-ring)`. Full keyboard nav (Tab/Shift+Tab; Enter activates primary; Esc closes modals/drawers). `aria-live="polite"` on Run status, trace step stream, toast region; `aria-live="assertive"` on Run errors. Every chart has table alternative reachable by tab. Network graph includes adjacency list panel. Browser font-size scaling up to 150% without layout breakage. All animations freeze under reduced motion.

**UX-DR13: App Shell** — Sidebar 256px (collapses to 72px icon rail under 1280px viewport). Each item: icon + label + optional count badge. Active: `bg-primary-soft`, `text-primary`, `border-l-2 border-primary`. Topbar 56px: wordmark + Tenant/Dept breadcrumb, global Run split-button (primary CTA), Escalation bell with count, theme toggle, avatar menu. Optional 320px right Inspector panel for context details (slides in on `[` shortcut).

**UX-DR14: Information Architecture** — Six top-level surfaces matching PRD §4 feature groups: Dashboard, Agents (List + Detail with 6 tabs), Workflows (List + Detail + Run View), Mini-Apps (Catalog + Generated App), Actions (Schedule + Event Triggers), Audit (Trail Explorer + Run Trace with Timeline + Collaboration Graph). Cross-cutting overlays: Command Palette (Cmd+K), Escalation Inbox (top-right bell drawer), Tenant/Department switcher (top-left persistent).

**UX-DR15: Dashboard Surface** — First screen after login. KPI strip (active Runs, pending escalations, today's Mini-App events), Escalation inbox preview (top 3 pending), Recent Runs list (last 5 with status + run-time + click-to-trace).

**UX-DR16: Agent Builder Surface** — List view (all Agents in Tenant with status pills, search, filter by Department). Detail view with 6 tabs: Identity (name, Department, system prompt), Knowledge Base (upload + RAG document list), Tools (registered Tools with schemas), API Integrations (registered connections), Prompt (system prompt editor), Model (provider picker, model picker, parameters).

**UX-DR17: Workflow Orchestrator Surface** — Definition view: name + natural-language description + optional constraints + Save. Run View: live trace of current Run with task cards, status transitions in real time, escalation handling panel when Run is `awaiting_human`. Workflow Runs list with filters.

**UX-DR18: Trace Dashboard Surface** — Toggleable views of same Audit Trail: Timeline (vertical cards with type/agent/latency/expand) and Collaboration Graph (Orchestrator node top, Agent nodes below, edges with Task type/status). Shareable by URL within Tenant.

**UX-DR19: Mini-App Builder Surface** — Catalog (all Mini-Apps in Tenant with schema, last activity, click-to-open). Generated Mini-App view: auto-rendered React UI from UI spec, gated by Visibility Tier, with live App Event stream sidebar showing row changes.

**UX-DR20: Actions Surface** — Two tabs: Schedule Triggers (list + create form with cron expression builder + target Workflow picker) and Event Triggers (list + create form with App Event filter, JSON-path predicate editor, target Workflow picker).

**UX-DR21: Audit Trail Explorer Surface** — Append-only log table (run_id, step_id, agent_id, timestamp, type, latency, model) with filters. Row click opens detail panel with full input/output JSON. Export button produces signed JSON download.

**UX-DR22: Command Palette (Cmd+K)** — Quick navigation, "Run workflow…" action, jump-to-agent, jump-to-trace. Keyboard-first. Opens with `Cmd+K` / `Ctrl+K`, closes with `Esc`.

**UX-DR23: Empty / Loading / Error States** — Every surface defines: Empty state (illustration + CTA), Loading state (skeleton matching final layout, not generic spinner), Error state (message + retry action). No silent failures.

**UX-DR24: Mobile Fallback (read-only)** — No layout work targets mobile. Mobile fallback is read-only: Run status view + escalation response only. Desktop-first commitment for primary surfaces (1440–1600px target).

### FR Coverage Map

| FR | Epic | Description |
|---|---|---|
| FR-1 | Epic 2 | Create and persist Specialist Agent |
| FR-2 | Epic 2 | Per-Agent Knowledge Base (upload + RAG) |
| FR-3 | Epic 2 | Per-Agent Tool configuration |
| FR-4 | Epic 2 | Per-Agent API Integration configuration |
| FR-5 | Epic 2 | Per-Agent Model selection |
| FR-6 | Epic 2 | Agent ownership + Department scoping |
| FR-7 | Epic 3 | Workflow definition (natural language) |
| FR-8 | Epic 3 | Dynamic task decomposition |
| FR-9 | Epic 3 | MCP-based task dispatch + aggregation |
| FR-10 | Epic 3 | Human-in-the-loop escalation |
| FR-11 | Epic 3 | Per-step feedback incorporation |
| FR-12 | Epic 4 | Agent-emitted entity schema + UI spec |
| FR-13 | Epic 4 | Auto-provisioned JSONB Namespace |
| FR-14 | Epic 4 | Auto-generated CRUD endpoints |
| FR-15 | Epic 4 | Auto-generated auth-gated UI |
| FR-16 | Epic 4 | Visibility Tier enforcement |
| FR-17 | Epic 4 | App Event emission to Action Bus |
| FR-18 | Epic 5 | Schedule Trigger (cron) |
| FR-19 | Epic 5 | Event Trigger (on App Event) |
| FR-20 | Epic 5 | Action Bus reliability |
| FR-21 | Epic 1 (sink/port) + Epics 2–6 (domain logging) + Epic 7 (full coverage validation) | Per-step Audit Trail logging |
| FR-22 | Epic 6 | Trace Dashboard — timeline view |
| FR-23 | Epic 6 | Trace Dashboard — collaboration graph |
| FR-24 | Epic 6 | Audit export (signed JSON) |
| FR-25 | Epic 1 | Multi-Tenant data isolation (RLS) |
| FR-26 | Epic 1 | Model Layer (provider-agnostic port) |
| FR-27 | Epic 1 | ReactJS SPA shell + dashboard |
| FR-28 | Epic 7 | Tenant bootstrapping (full demo data) |

**All 28 FRs mapped.**

## Epic List

### Epic 1: Foundation & Contracts *(Sequential — Unlocks Parallelism)*

A developer can clone the repo, run `docker-compose up`, start both backend and frontend, log into a seeded Tenant, and see the dashboard shell — with stable TypeScript/Python interfaces for all 5 downstream feature streams to develop against.

**FRs covered:** FR-21 (audit sink + port — foundational), FR-25 (RLS multi-tenancy), FR-26 (Model Layer port + Anthropic adapter), FR-27 (SPA shell + routing + design tokens + dashboard)
**Additional:** AR-1 (starter template), AR-2 through AR-15 (all architecture decisions baked in)
**UX:** UX-DR1–15, UX-DR22–23 (foundation layer)
**Parallel-unlock criteria:**
- All `core/ports/*.py` interfaces defined (`LlmPort`, `AuditPort`, `McpClientPort`, plus new ones: `AgentProviderPort`, `WorkflowRunPort`, `MiniAppProvisionerPort`, `TriggerRegistryPort`)
- TypeScript API client contracts generated from FastAPI OpenAPI schema
- Mock/stub implementations returning canned data for every port
- Database schema for `tenants`, `users`, `departments`, `audit_trail` (with RLS)
- Frontend shell with sidebar, routing, design tokens, empty-state patterns

### Epic 2: Specialist Agent Builder *(Parallel Stream)*

A user can configure a Specialist Agent end-to-end — identity, Department-scoped Knowledge Base, Tools with schemas, API Integrations, and per-Agent Model selection — and persist it as a Tenant-scoped record ready for Workflow execution.

**FRs covered:** FR-1, FR-2, FR-3, FR-4, FR-5, FR-6
**UX:** UX-DR16 (Agent Builder surface, 6 tabs)
**Contract consumed:** `tenant` module, `LlmPort`, `McpClientPort`
**Contract published:** `AgentProviderPort` (list/get/dispatch) — consumed by Epic 3
**Parallel-safe:** Develops against `McpClientPort` stub for KB retrieval; Orchestrator doesn't need to exist yet.

### Epic 3: Workflow Orchestrator & Human-in-the-Loop *(Parallel Stream)*

A user can define a Workflow in natural language, kick off a Run, watch the Orchestrator decompose it into Tasks dispatched to Specialist Agents, and resolve escalations through the live Run view when conflicts arise.

**FRs covered:** FR-7, FR-8, FR-9, FR-10, FR-11
**UX:** UX-DR17 (Workflow Orchestrator surface with Definition + Run views)
**Contract consumed:** `AgentProviderPort`, `LlmPort`, `AuditPort`
**Contract published:** `WorkflowRunPort` (start/status/escalate) — consumed by Epic 5
**Parallel-safe:** Develops against `AgentProviderPort` stub (canned agent responses). Real Agent integration happens at integration time.

### Epic 4: Mini-App Builder & Visibility Tier Enforcement *(Parallel Stream)*

A Specialist Agent (or the Orchestrator) can emit an entity schema and have the platform auto-provision a fully-functional Mini-App — JSONB namespace, CRUD endpoints, auth-gated React UI, and App Event emission — all gated by row-level Visibility Tier rules.

**FRs covered:** FR-12, FR-13, FR-14, FR-15, FR-16, FR-17
**UX:** UX-DR19 (Mini-App Builder surface: catalog + generated app view)
**Contract consumed:** `audit`, RLS framework, App Event Bus (Redis stream)
**Contract published:** `MiniAppProvisionerPort` (emit schema → app), App Event stream schema — consumed by Epic 5
**Parallel-safe:** Develops against canned schemas (no real Orchestrator needed). Atomic provisioning per AD-8 self-contained.

### Epic 5: Actions, Triggers & Event-Driven Automation *(Parallel Stream)*

A user can register Schedule Triggers (cron) and Event Triggers (App Event matches) so that follow-on Workflows fire automatically — closing the loop (App change → Event → next Workflow Run).

**FRs covered:** FR-18, FR-19, FR-20
**UX:** UX-DR20 (Actions surface)
**Contract consumed:** `WorkflowRunPort` (to fire runs), App Event stream (from Epic 4)
**Contract published:** `TriggerRegistryPort` — used by integration epic
**Parallel-safe:** Develops against `WorkflowRunPort` stub and a synthetic App Event feed. Cron + event matching logic is fully isolated.

### Epic 6: Trace Dashboard & Audit Provenance *(Parallel Stream)*

A judge or auditor can open any Workflow Run, switch between timeline and collaboration-graph views of the same Audit Trail, expand any step for full input/output detail, and export a signed JSON audit package satisfying the banking-audit obligation.

**FRs covered:** FR-22, FR-23, FR-24 (FR-21 implemented in Epic 1; Epics 2–5 add domain-specific audit calls as they build features)
**UX:** UX-DR18 (Trace Dashboard), UX-DR21 (Audit Trail Explorer), UX-DR24 (mobile read-only fallback)
**Contract consumed:** `audit_trail` table (read-only), FR-21 entries written by all modules
**Parallel-safe:** Develops against synthetic audit fixtures (canned Run data with 20+ varied steps). Doesn't need real Runs — just realistic Audit Trail entries.

### Epic 7: Integration & Demo Readiness *(Sequential — After Parallel Streams)*

A judge watches the full closed-loop demo: Linh configures Agent → Workflow Run → Mini-App auto-generated → row edit fires App Event → Event Trigger fires next Run — all visible in the Trace Dashboard. Bootstrap script produces a fresh Tenant in <60s.

**FRs covered:** FR-28 (Tenant bootstrapping — full demo data, not just minimal seed)
**Work:**
- Replace all stubs with real implementations (wire `AgentProviderPort` → Epic 2, `WorkflowRunPort` → Epic 3, etc.)
- Closed-loop end-to-end integration test (Playwright UJ-1 + UJ-2)
- Demo bootstrap script with synthetic loan cases, 2 Departments, pre-configured Workflow
- Performance validation against NFR-1 through NFR-10

---

### Parallel Execution Plan

```
Sprint 1:  [ Epic 1: Foundation & Contracts          ]     ← 2 devs paired
                    ↓ (contracts land)
Sprint 2:  [ Epic 2 ][ Epic 3 ][ Epic 4 ][ Epic 5 ][ Epic 6 ]   ← 5 parallel streams
Sprint 3:  [ Epic 2 ][ Epic 3 ][ Epic 4 ][ Epic 5 ][ Epic 6 ]   ← parallel continues
                    ↓ (streams complete)
Sprint 4:  [ Epic 7: Integration & Demo Readiness    ]     ← 2 devs paired
```

### Recommended Team Allocation (5 devs)

| Stream | Complexity | Suggested |
|---|---|---|
| Epic 2 — Agent Builder | Medium (mostly CRUD + 1 MCP integration) | 1 dev |
| Epic 3 — Orchestrator | Large (LLM decomposition, state machines, escalation) | 1–2 devs |
| Epic 4 — Mini-App Builder | Large (auto-provisioning, dynamic UI generation, RLS) | 1–2 devs |
| Epic 5 — Actions | Small (3 FRs, well-understood patterns) | 1 dev (could pair with integration early) |
| Epic 6 — Trace Dashboard | Small-Medium (mostly UI + 2 data views) | 1 dev |

---

## Epic 1: Foundation & Contracts

A developer can clone the repo, run `docker-compose up`, start both backend and frontend, log into a seeded Tenant, and see the dashboard shell — with stable TypeScript/Python interfaces for all 5 downstream feature streams to develop against.

### Story 1.1: Repo Skeleton & Infrastructure Setup

As a **developer**,
I want **a clean monorepo skeleton with Postgres and Redis running via docker-compose**,
So that **I can start backend and frontend work without spending time on environment setup**.

**Acceptance Criteria:**

**Given** a clean clone of the repository on a developer machine with Docker installed
**When** the developer runs `docker-compose up`
**Then** Postgres 18 and Redis 7.4+ containers start and pass healthchecks
**And** `backend/` contains `app/main.py`, `pyproject.toml` pinned to AR-13 stack (Python 3.13, FastAPI 0.139.x, SQLAlchemy 2.x, Pydantic 2.x, Alembic, arq 0.26+, mcp v1.x, anthropic 0.114.0)
**And** `frontend/` contains a Vite 8 + React 19 + TypeScript 7.x + Tailwind CSS 4 setup with `package.json` and `vite.config.ts`
**And** `infra/docker-compose.yml` exposes Postgres on `:5432` and Redis on `:6379` with persistent volumes
**And** `GET /health` on the FastAPI backend returns `200` with `{"status": "ok"}`
**And** `npm run dev` on the frontend starts Vite dev server on `:5173` without errors
**And** the directory structure matches AR-1 structural seed (`backend/app/{modules,core,bootstrap}`, `backend/tests/{unit,integration,e2e}`, `frontend/src/{routes,components,hooks,lib}`, `infra/`, `docs/`)

### Story 1.2: Multi-Tenant Data Layer with Postgres RLS

As a **backend developer**,
I want **every persisted table to enforce tenant isolation at the Postgres Row-Level Security layer**,
So that **no query — even a misconfigured one — can leak another Tenant's rows**.

**Acceptance Criteria:**

**Given** the `tenants`, `users`, and `departments` tables exist with `tenant_id UUID NOT NULL` columns
**When** a database session sets `SET LOCAL app.tenant_id = '<tenant_a_id>'` and queries any tenant-scoped table
**Then** only rows with `tenant_id = '<tenant_a_id>'` are returned
**And** a direct SQL query attempting to read TenantB rows under TenantA's session returns an empty result set, never TenantB data
**And** the application role has `BYPASSRLS` revoked; only the bootstrap/migration role can bypass (AD-2)
**And** all entity IDs use UUID v7 (time-ordered); no autoincrement columns exist (AR-14)
**And** all timestamps are UTC ISO 8601 with milliseconds, stored as `timestamptz` (AR-14)
**And** an Alembic migration creates the tables and the RLS policies idempotently
**And** a test verifies cross-tenant query returns empty under both ORM and raw SQL paths

### Story 1.3: Auth & Tenant Context Middleware

As a **backend developer**,
I want **FastAPI middleware that authenticates requests and sets the tenant contextvar from the JWT**,
So that **downstream domain code can read `tenant_context.get()` without passing `tenant_id` as a function argument**.

**Acceptance Criteria:**

**Given** a User row exists with a hashed password (Argon2)
**When** the User posts valid credentials to `POST /auth/login`
**Then** the response returns a JWT containing `user_id`, `tenant_id`, `department_id`, and role claims
**And** the JWT expires per a configurable TTL
**When** an authenticated request hits any protected endpoint
**Then** FastAPI middleware parses the JWT, verifies the signature, and sets `tenant_context.ContextVar` with `tenant_id`, `user_id`, `department_id`, `role`
**And** the same contextvar is read by the SQLAlchemy session to issue `SET LOCAL app.tenant_id` (AD-10)
**When** an unauthenticated request hits a protected endpoint
**Then** the response is `401` with the standard error envelope `{error: {code: "UNAUTHENTICATED", message, details, trace_id}}`
**When** a request has a valid JWT but the User has been deactivated
**Then** the response is `401` with `code: "ACCOUNT_DEACTIVATED"`
**And** `GET /auth/me` returns the current User's profile (id, email, tenant_id, department_id, role)
**And** a test verifies that protected endpoints under two different JWTs never cross tenant boundaries

### Story 1.4: Core Ports & API Error Envelope

As a **backend developer on any downstream stream**,
I want **all hexagonal port interfaces defined and a generated TypeScript client**,
So that **I can develop my module against stable contracts without waiting for other modules**.

**Acceptance Criteria:**

**Given** the `core/ports/` directory
**When** a developer inspects it
**Then** the following abstract interfaces exist with method signatures and Pydantic models: `LlmPort` (`complete`, `stream`, `embed`), `AuditPort` (`log`), `McpClientPort` (`call_tool` with mandatory `tenant_id` + `department_id` per AD-11), `AgentProviderPort` (`list_agents`, `get_agent`, `dispatch_task`), `WorkflowRunPort` (`start_run`, `get_run_status`, `escalate_run`), `MiniAppProvisionerPort` (`provision`, `list_apps`, `get_app`), `TriggerRegistryPort` (`register_schedule`, `register_event`, `list_triggers`)
**And** every port has a stub implementation in `core/ports/stubs/` returning realistic canned data (not `None`)
**When** any API endpoint returns an error
**Then** the response body matches `{error: {code: string, message: string, details: object, trace_id: uuid}}` exactly — no exceptions (AR-14)
**When** any API endpoint returns success
**Then** the response body matches `{data: <payload>, error: null, meta: {pagination?: {total, page, limit}}}` (AR-14)
**And** FastAPI OpenAPI schema is exported at `/openapi.json` and a build script generates a TypeScript client into `frontend/src/lib/api-client/`
**And** a test verifies every endpoint conforms to the envelope (success + error paths)

### Story 1.5: Audit Sink & Append-Only Trail

As a **backend developer**,
I want **a single audit sink that is the only path to write `audit_trail` and that crashes the calling Run on failure**,
So that **trace completeness outranks Run completion per the banking-audit obligation**.

**Acceptance Criteria:**

**Given** the `audit_trail` table with columns `{run_id, step_id, agent_id, ts, type, input, output, latency_ms, model}` (FR-21 schema, AR-14)
**When** a database role attempts `UPDATE` or `DELETE` on `audit_trail`
**Then** the operation is rejected at the DB level (permissions revoked; only `INSERT` granted to app role) (AD-4)
**And** the only application code path that writes to `audit_trail` is `audit.log(entry)` in `core/ports/audit.py`
**When** a Run step calls `audit.log(entry)` and the underlying DB write fails (DB down, constraint violation)
**Then** the calling Workflow Run transitions to `failed` status — never silently drops the entry (AD-4)
**And** the failure is itself logged to platform logs with `run_id` and `trace_id` for diagnosis
**When** a Run crashes mid-execution
**Then** all `audit.log()` calls made before the crash are persisted (append-only durability)
**And** every entry carries UTC ISO 8601 timestamp with milliseconds and UUID v7 `step_id`
**And** the `audit_trail` table itself is tenant-scoped with RLS (Story 1.2 applies)

### Story 1.6: Model Layer Port + Anthropic Adapter

As a **backend developer building Agent or Orchestrator features**,
I want **a provider-agnostic Model Layer with the Anthropic adapter implemented**,
So that **Agents can call any LLM through a single interface without coupling to a specific provider**.

**Acceptance Criteria:**

**Given** the `LlmPort` interface from Story 1.4
**When** a developer implements `core/adapters/anthropic.py`
**Then** the adapter exposes `complete(messages, model, parameters)`, `stream(messages, model, parameters)`, and `embed(text, model)`
**And** the adapter wraps the `anthropic` 0.114.0 SDK and never lets domain code import the SDK directly (AD-7)
**When** domain code calls `llm.complete(...)` with `{provider: "anthropic", model_name: "claude-...", parameters: {...}}`
**Then** the call routes through `LlmPort` to the Anthropic adapter and returns `{content, usage: {input_tokens, output_tokens}, latency_ms}`
**And** the call logs `{provider, model, prompt_token_count, completion_token_count, latency_ms}` to `audit_trail` via `audit.log()` (NFR-5)
**When** the configured provider is missing (e.g., API key not set)
**Then** the error surfaces at run time, not config time, with a clear message in `audit_trail` (FR-5 consequence)
**And** a missing provider in one Agent does not crash other Agents configured with other providers (FR-26)
**And** placeholder adapter files exist for `openai.py`, `google.py`, `ollama.py` with `NotImplementedError` raised on call — ready for parallel-stream implementation
**And** a test verifies that adding a new provider requires no changes to Agent, Orchestrator, or Mini-App code

### Story 1.7: arq Background Job Foundation

As a **backend developer building Orchestrator, Actions, or Triggers**,
I want **arq worker infrastructure with tenant context materialized across the worker boundary**,
So that **background jobs run with correct RLS isolation and don't crash on missing tenant context**.

**Acceptance Criteria:**

**Given** Redis 7.4+ is configured as the arq broker
**When** a developer runs the arq `WorkerSettings`
**Then** the worker connects to Redis and begins polling for jobs
**When** domain code enqueues a background job (e.g., `enqueue_workflow_run(workflow_id, tenant_id, ...)`)
**Then** the enqueuer captures `tenant_id` (and `department_id` if relevant) from the current contextvar and serializes them into the arq job kwargs (AD-10)
**When** the arq worker dequeues a job
**Then** the worker function's first action deserializes `tenant_id` from kwargs, sets `tenant_context.ContextVar`, and issues `SET LOCAL app.tenant_id` on its DB connection before any domain work (AD-10)
**And** if the payload is missing `tenant_id`, the worker raises immediately with a structured error and does not execute domain code
**When** a job is configured as a `cron_jobs` entrypoint (Schedule Trigger fan-out pattern)
**Then** the cron job runs under `BYPASSRLS`, enumerates matching tenants, and enqueues one per-tenant job with materialized `tenant_id` for each (AD-10)
**And** a test verifies that two jobs from different tenants enqueued back-to-back do not leak tenant context to each other
**And** no Celery, APScheduler, or background threads exist in domain code — arq is the only async job system (AR-14)

### Story 1.8: Frontend Shell, Design Tokens & Login

As a **user**,
I want **to log into VAIC and land on a shell with consistent design language**,
So that **every surface I navigate to feels like the same product**.

**Acceptance Criteria:**

**Given** the frontend setup from Story 1.1
**When** a developer applies UX-DR1 (design tokens)
**Then** `frontend/src/styles/tokens.css` contains CSS custom properties for the hybrid Indigo/Slate/Emerald palette with full light/dark mode variants
**And** no hardcoded hex values exist anywhere in the codebase — all colors reference tokens (UX-DR1)
**When** a developer applies UX-DR2 (typography)
**Then** Plus Jakarta Sans loads for UI text (32px → 12px scale, 14px base) and JetBrains Mono loads for code/IDs
**And** `font-display: swap` is set on both; only essential weights are preloaded
**When** a developer applies UX-DR13 (app shell)
**Then** the layout renders a 256px sidebar (collapses to 72px icon rail under 1280px viewport), a 56px topbar, and an optional 320px right Inspector panel
**And** the sidebar shows nav items: Dashboard, Agents, Workflows, Mini-Apps, Actions, Audit, Settings (UX-DR14)
**And** active item shows `bg-primary-soft`, `text-primary`, `border-l-2 border-primary`; hover shows `bg-surface-muted`
**And** the topbar shows the wordmark + Tenant/Department breadcrumb + global Run split-button + Escalation bell + theme toggle + avatar menu
**When** an unauthenticated user visits any route
**Then** they are redirected to `/login`
**And** the login page accepts email + password, calls `POST /auth/login`, stores the JWT, and redirects to `/dashboard`
**And** failed login shows an inline error in `--color-destructive`
**And** the entire shell respects `prefers-color-scheme` and the manual theme toggle (UX-DR1)

### Story 1.9: Component Primitives & State System

As a **frontend developer on any downstream stream**,
I want **a complete component primitive library and authoritative state system**,
So that **I can build feature surfaces with consistent UI without re-implementing basics**.

**Acceptance Criteria:**

**Given** the design tokens from Story 1.8
**When** a developer implements UX-DR3 (buttons)
**Then** the Button component supports 5 variants: Primary, Secondary, Ghost, Destructive, Icon (36×36 with mandatory `aria-label` + tooltip)
**And** min height is 36px with 8px padding-y, 16px padding-x
**And** only one Primary CTA exists per view (enforced via lint rule or runtime warning)
**When** a developer implements UX-DR4 (status pills)
**Then** the StatusPill component renders icon + label for 6 states: Pending (amber Clock), Running (sky Loader-spin), Success (emerald Check), Error (rose X), Escalated (amber-600 AlertTriangle), Draft (slate-400 Pencil)
**And** the same icon + color mapping is used everywhere these states appear (UX-DR11)
**When** a developer implements UX-DR5 through UX-DR8 (cards, tables, code blocks, forms)
**Then** Cards have `1px` border with `--color-border`, no default shadow, `sm` shadow when interactive
**And** Tables support sticky headers, row hover (`bg-surface-muted`), selected row (`bg-primary-soft` with left border), bulk action bar
**And** Code/JSON blocks have copy button top-right with `rehype-highlight` or `shiki` syntax highlighting
**And** Forms show labels above inputs (never placeholder-only), mark required fields with `*` in destructive color, validate inline on blur (not keystroke)
**When** a developer implements UX-DR9 (motion)
**Then** the motion tokens define durations (hover 120ms, modal 200ms, Run status 240ms, trace step 180ms fade + 4px slide-up, escalation toast 280ms, page transition 160ms) with the easing curve `cubic-bezier(0.16, 1, 0.3, 1)` for modals
**And** all animations freeze under `prefers-reduced-motion`, replaced with instant transitions
**And** trace timeline updates are interruptible — new step cancels in-flight animation
**And** no animation touches `width/height/top/left` — only `transform` and `opacity`
**When** a developer implements UX-DR10 (iconography)
**Then** `lucide-react` is the only icon library, with 1.5px stroke globally
**And** semantic assignments are locked: Bot=Agent, Workflow=Orchestrator, LayoutGrid=Mini-App, Activity=Trace, Zap=Actions, BookOpen=KB, Wrench=Tool, Plug=API Integration, Cpu=Model, Building2=Department, Landmark=Tenant, Play=Run, AlertTriangle=Escalation, Radio=Live
**And** no emojis are used as structural icons
**When** a developer implements UX-DR12 (accessibility)
**Then** text contrast ≥ 4.5:1 and UI glyph contrast ≥ 3:1, verified independently for dark mode
**And** focus rings render as `box-shadow: 0 0 0 2px var(--color-bg), 0 0 0 4px var(--color-ring)` visible on any background
**And** full keyboard nav works (Tab/Shift+Tab; Enter activates primary; Esc closes modals/drawers)
**And** `aria-live="polite"` is set on Run status, trace step stream, toast region; `aria-live="assertive"` on Run errors
**And** browser font-size scaling up to 150% does not break layout

### Story 1.10: Dashboard Surface

As a **logged-in user**,
I want **a dashboard that orients me to what's running, what needs my attention, and what ran recently**,
So that **I can decide what to do next without hunting through menus**.

**Acceptance Criteria:**

**Given** the shell and primitives from Stories 1.8 and 1.9
**When** a user navigates to `/dashboard`
**Then** the page renders three sections per UX-DR15: KPI strip, Escalation inbox preview, Recent Runs list
**And** the KPI strip shows three cards: Active Runs (count), Pending Escalations (count), Today's Mini-App Events (count) — populated from mock data via TanStack Query (real data wired in Epics 3, 5, 6)
**And** the Escalation inbox preview shows the top 3 pending items with Run name, escalation reason, and "Open" affordance (mock data; real wiring in Epic 3)
**And** the Recent Runs list shows the last 5 Runs with name, status pill, run-time, and click-to-trace affordance (mock data; real wiring in Epic 3)
**When** any section has zero items
**Then** an empty state renders per UX-DR23 (illustration + CTA)
**When** any section is loading
**Then** a skeleton matching the final layout renders (not a generic spinner)
**When** any section fails to load
**Then** an error state renders with the error message and a retry action
**And** the dashboard is the default route after login

### Story 1.11: Command Palette (Cmd+K)

As a **power user**,
I want **a Cmd+K palette for quick navigation and actions**,
So that **I can move through the platform without taking my hands off the keyboard**.

**Acceptance Criteria:**

**Given** the shell from Story 1.8
**When** a user presses `Cmd+K` (macOS) or `Ctrl+K` (Windows/Linux) anywhere in the app
**Then** a Command Palette modal opens with a search input focused
**And** the palette shows a list of navigation commands: Go to Dashboard, Go to Agents, Go to Workflows, Go to Mini-Apps, Go to Actions, Go to Audit, Go to Settings
**When** the user types a query
**Then** the list filters by fuzzy match on command name
**When** the user selects a navigation command (Enter or click)
**Then** the palette closes and the router navigates to the target route
**When** the user presses `Esc`
**Then** the palette closes without action (UX-DR1 escape-routes)
**And** the palette includes a placeholder "Run workflow…" command that surfaces a "No workflows yet" message until Epic 3 lands (extension point for downstream streams to register commands)
**And** a registry API exists so downstream epics can register their own commands (e.g., "Run workflow X" in Epic 3, "Export audit" in Epic 6)

### Story 1.12: Minimal Tenant Seed Script (Bootstrap Lite)

As a **developer setting up a working environment**,
I want **an idempotent script that seeds one Tenant, one User per role, and two Departments**,
So that **I can log in and start developing downstream features against realistic data**.

**Acceptance Criteria:**

**Given** a fresh database with migrations applied
**When** a developer runs `python scripts/bootstrap_demo_tenant.py` (or `uv run bootstrap_demo_tenant`)
**Then** the script creates (under `BYPASSRLS`): 1 Tenant named "SHB Demo", 2 Departments ("Credit", "Operations"), 1 User per role (builder, manager, operator) with known credentials documented in `README.md`
**And** each User is associated with the Tenant and assigned a Department
**And** all entity IDs are UUID v7
**When** the script runs a second time
**Then** it does not duplicate records — idempotent (detects existing Tenant by name and skips or updates)
**When** the script completes
**Then** the developer can log in via the frontend login page with the seeded credentials and land on `/dashboard`
**And** the script runs in under 10 seconds (this is the dev bootstrap, not the full demo; full demo with Workflows + Mini-Apps + synthetic loan cases is Epic 7 / FR-28)
**And** the script logs progress to stdout with clear success/failure indicators

---

## Epic 2: Specialist Agent Builder

A user can configure a Specialist Agent end-to-end — identity, Department-scoped Knowledge Base, Tools with schemas, API Integrations, and per-Agent Model selection — and persist it as a Tenant-scoped record ready for Workflow execution.

### Story 2.1: Agent CRUD, Identity & Department Scoping

As a **user with builder role**,
I want **to create, read, update, and list Specialist Agents scoped to my Tenant and Department**,
So that **I can manage the Agent inventory that the Orchestrator will dispatch Tasks to**.

**Acceptance Criteria:**

**Given** an authenticated User with builder role in TenantA, DepartmentX
**When** the User posts `POST /agents` with `{name, department_id: <DeptX>, system_prompt}`
**Then** the response is `201` with the new Agent's `id` (UUID v7), `tenant_id`, `department_id`, `owner_id` (= caller), `created_at`, `version`
**And** `GET /agents/{id}` returns the same record
**And** the Agent record is unreadable from TenantB — the response is `404` (not `403`, to avoid confirming existence) (FR-1)
**When** the User lists `GET /agents` with no Department filter
**Then** only Agents in the caller's Tenant are returned
**And** filtering by Department returns only Agents in that Department within the caller's Tenant
**When** a User who is not the `owner_id` and does not have builder role in the same Department attempts `PATCH /agents/{id}`
**Then** the response is `403` with `code: "FORBIDDEN"`
**And** the same scoping rules apply to `DELETE` (soft-delete only; never hard delete — preserves audit referential integrity)
**And** every CRUD operation emits an `audit.log()` entry with `type: "agent.created" | "agent.updated" | "agent.deleted"` (FR-21, AD-4)
**And** the `agents` table has RLS policies from Story 1.2 applied — direct SQL cross-tenant query returns empty

### Story 2.2: Agent List & Detail Shell with Identity Tab

As a **user**,
I want **a list of all Agents in my Tenant and a detail view with tabbed configuration**,
So that **I can navigate the Agent inventory and edit an Agent's identity without hunting through menus**.

**Acceptance Criteria:**

**Given** the Agent endpoints from Story 2.1
**When** the user navigates to `/agents`
**Then** the page shows a searchable list of Agents in the caller's Tenant, each row showing name, Department badge, status (Draft/Active), owner, last-modified
**And** the list supports filtering by Department via a header dropdown
**And** the list supports text search on name (debounced, 200ms)
**And** an empty state renders when there are zero Agents (UX-DR23)
**When** the user clicks a row or "New Agent"
**Then** the detail view opens at `/agents/$id` with a 6-tab navigation: Identity, Knowledge Base, Tools, API Integrations, Prompt, Model (UX-DR16)
**And** the Identity tab is the default landing tab
**And** the Identity tab shows a form: Name (text, required), Department (select, required), System Prompt (textarea, required), Status (Draft/Active toggle)
**And** the form marks required fields with `*` in destructive color, validates on blur, shows inline errors (UX-DR8)
**When** the user edits the form and clicks Save
**Then** a `PATCH /agents/{id}` fires; success shows a toast; failure shows an inline error
**And** an unsaved-changes indicator (dirty dot in tab) appears when the form is modified and not saved
**And** navigating away with unsaved changes shows a confirmation dialog

### Story 2.3: Per-Agent Model Selection & Prompt Editing

As a **user configuring a Specialist Agent**,
I want **to pick the LLM provider and model for my Agent and refine the system prompt**,
So that **the Agent uses the right model for its task without code changes**.

**Acceptance Criteria:**

**Given** the Model Layer from Story 1.6 with the Anthropic adapter implemented
**When** the user opens the Model tab
**Then** a Provider dropdown lists runtime-configured providers (at minimum: Anthropic; placeholders for OpenAI, Google, Ollama grayed out with "Not configured")
**And** selecting a Provider populates a Model dropdown with that provider's available models
**And** a Parameters section allows optional overrides (temperature, max_tokens) with sensible defaults
**When** the user saves the Model tab
**Then** the Agent record stores `{provider, model_name, parameters}` as data, never as code (AD-7)
**And** changing the Model does not require any code changes — only a config update (FR-5)
**When** the user opens the Prompt tab
**Then** a system prompt editor renders (monospace textarea with syntax highlighting for prompt directives, e.g., `{{tool:rag.search}}`, `{{kb:agent_id}}`)
**And** the editor shows a character count and warns if the prompt exceeds the selected model's context window
**And** saving the Prompt tab persists to the Agent record's `system_prompt` field
**When** an Agent runs and its configured provider is missing (e.g., API key revoked)
**Then** the error surfaces at run time, not config time, with a clear message in `audit_trail` (FR-5 consequence)
**And** a missing provider in one Agent does not crash other Agents configured with other providers (FR-26)

### Story 2.4: Knowledge Base Upload & Storage

As a **user configuring a Specialist Agent**,
I want **to upload policy/SOP documents to my Agent's Knowledge Base**,
So that **the Agent can ground its responses in our bank's documented procedures**.

**Acceptance Criteria:**

**Given** an Agent exists in DepartmentX and the `McpClientPort` from Story 1.4 has a stub returning successful ingestion
**When** the user opens the Knowledge Base tab and uploads a document (PDF, TXT, Markdown, DOCX) up to 20MB
**Then** the upload completes within 30s per document
**And** the platform chunks, embeds, and indexes the document via `McpClientPort` with mandatory `tenant_id` + `department_id` matching the Agent's Department (AD-11)
**And** the document appears in the KB document list with status: Processing → Indexed (or Failed with reason)
**When** the upload exceeds 20MB
**Then** the upload is rejected client-side with a clear message before reaching the backend
**When** the upload exceeds 30s
**Then** the upload is aborted with a timeout error and the document status shows "Failed: Timeout"
**When** the user deletes a document
**Then** the document and all its chunks/embeddings are removed from the index (via `McpClientPort`)
**And** every upload/delete emits an `audit.log()` entry with `type: "kb.document.uploaded" | "kb.document.deleted"` (FR-21)
**And** documents are limited to policy/regulation/SOP content — no real customer PII (NFR-9, banking data sensitivity)
**And** a placeholder for the parallel-team MCP server's `rag.search` is invoked through `McpClientPort` (the MCP server itself is built by another team per AD-3)

### Story 2.5: Knowledge Base Retrieval at Runtime

As a **Specialist Agent running inside a Workflow**,
I want **to retrieve cited passages from my Department-scoped Knowledge Base**,
So that **my responses are grounded in bank policy without leaking other Departments' documents**.

**Acceptance Criteria:**

**Given** documents are indexed in DepartmentX's KB (Story 2.4)
**When** runtime code calls `kb_search(agent_id, query)` (the Agent-internal retrieval function)
**Then** the call routes through `McpClientPort.call_tool("rag.search", {agent_id, query, tenant_id, department_id})` with the Agent's own `department_id` (AD-11)
**And** the McpClientPort enforces client-side that the `department_id` parameter matches the calling Agent's `department_id`; mismatch raises before hitting the network
**And** the result is a list of `{passage, document_name, chunk_reference, score}` entries
**When** a Credit-department Agent attempts a direct `kb_search` against an HR-department KB
**Then** the result set is empty — never the HR documents (FR-2)
**And** the retrieval is logged to `audit_trail` with `type: "kb.retrieval"`, `input: {agent_id, query}`, `output: {passage_count, top_score}` (FR-21)
**And** the retrieval function is exposed via `AgentProviderPort` so the Orchestrator (Epic 3) can dispatch retrieval Tasks to Specialist Agents

### Story 2.6: Per-Agent Tool Configuration

As a **user configuring a Specialist Agent**,
I want **to register Tools with structured input/output schemas that the Agent can invoke during a Workflow Run**,
So that **the Agent can take actions beyond text generation, validated against a contract**.

**Acceptance Criteria:**

**Given** an Agent exists and the user opens the Tools tab
**When** the user clicks "New Tool" and provides `{display_name, header (including auth), input_schema (JSON Schema), output_schema (JSON Schema), optional embedded_python}`
**Then** the Tool is registered against the Agent with a UUID v7 `tool_id`
**And** both schemas validate against JSON Schema draft 2020-12
**When** an Agent invokes a registered Tool during a Workflow Run
**Then** every invocation validates the input against `input_schema`; mismatched calls return a structured error to the Orchestrator and are logged to `audit_trail` with `type: "tool.invoked"` or `type: "tool.rejected"` (FR-3)
**And** output that fails `output_schema` is rejected and logged (FR-3)
**When** a Tool has embedded Python
**Then** the Python executes in a subprocess sandbox: no network egress, restricted builtins, 10s CPU cap, 128MB memory cap (AR-14)
**And** input is passed via stdin, output read from stdout
**And** a sandbox timeout or memory breach terminates the subprocess and logs `type: "tool.sandbox_violation"` to `audit_trail`
**And** the Tools tab UI provides a JSON Schema editor (e.g., monaco-editor) with live validation
**And** a "Test Tool" affordance lets the user invoke the Tool with sample input and see the output (useful during development)

### Story 2.7: Per-Agent API Integration Configuration

As a **user configuring a Specialist Agent**,
I want **to register reusable API Integrations that my Tools can call**,
So that **my Agent can interact with stubbed Gmail, Calendar, or bank-core endpoints without re-specifying the connection per Tool**.

**Acceptance Criteria:**

**Given** an Agent exists and the user opens the API Integrations tab
**When** the user clicks "New Integration" and provides `{name, base_url, auth_header (stored, not displayed in full), schema}`
**Then** the Integration is registered against the Agent with a UUID v7 `integration_id`
**And** the `auth_header` is stored encrypted at rest (per AR-14 stored credentials, never hard-coded)
**And** the Integration is selectable from any Tool on that Agent via an "API Integration" dropdown in the Tool editor
**When** a Tool invokes the Integration during a Workflow Run
**Then** the request is made to `{base_url}/{path}` with the stored auth header attached
**And** the call is logged to `audit_trail` with `type: "integration.called"`, `input: {integration_id, path, method}`, `output: {status_code, latency_ms}` (FR-21)
**And** for MVP, Integrations point only at stubbed FastAPI endpoints owned by the demo (FR-4, §5 non-goal: live OAuth is out of scope)
**And** an integration's auth header is never logged in `audit_trail` — only metadata (integration_id, status, latency) is captured (NFR-9)
**And** the API Integrations tab UI lists all integrations with name, base_url (truncated), last-used timestamp
**And** a "Test Integration" affordance pings `GET {base_url}/health` (or equivalent) and shows connected/disconnected status

### Story 2.8: Agent Builder Surface Integration

As a **user configuring an Agent end-to-end**,
I want **the six configuration tabs to behave as one cohesive surface**,
So that **I can move between identity, KB, tools, integrations, prompt, and model without losing context**.

**Acceptance Criteria:**

**Given** the tab UIs from Stories 2.2 through 2.7
**When** the user opens `/agents/$id`
**Then** all six tabs are visible in the navigation: Identity, Knowledge Base, Tools, API Integrations, Prompt, Model
**And** the tab badge shows count where relevant (e.g., KB tab shows "3 documents", Tools tab shows "5 tools", Integrations tab shows "2 integrations")
**And** an unsaved-changes dot appears on a tab when its form is dirty
**When** the user switches tabs with unsaved changes
**Then** a confirmation dialog appears: "Save changes before leaving?" with Save / Discard / Cancel options
**When** any tab fails to load its data
**Then** the tab body shows an error state per UX-DR23 (message + retry)
**When** any tab is loading
**Then** a skeleton matching the tab's final layout renders
**When** the Agent has never been saved (new Agent flow)
**Then** the Identity tab is the only enabled tab; the others are disabled until the Agent is saved once (creates the record)
**And** the detail view header shows the Agent name, Department badge, status pill (Draft/Active), and a global "Save All" button if any tab has unsaved changes
**And** keyboard nav works across tabs (Tab/Shift+Tab, Enter to activate, arrow keys to switch tabs) per UX-DR12
**And** the surface is fully responsive within the desktop-first commitment (UX-DR13: 1440–1600px target; collapses Inspector under 1280px)

---

## Epic 3: Workflow Orchestrator & Human-in-the-Loop

A user can define a Workflow in natural language, kick off a Run, watch the Orchestrator decompose it into Tasks dispatched to Specialist Agents, and resolve escalations through the live Run view when conflicts arise.

### Story 3.1: Workflow Definition CRUD & UI

As a **user with builder role**,
I want **to create and edit Workflows described in natural language**,
So that **the Orchestrator can dynamically decompose my intent into Tasks at run time without hard-coded routing**.

**Acceptance Criteria:**

**Given** an authenticated User with builder role
**When** the User posts `POST /workflows` with `{name, description, constraints?: string[]}`
**Then** the response is `201` with the new Workflow's `id` (UUID v7), `tenant_id`, `owner_id`, `created_at`, `version`
**And** the description is treated as a hint to the Orchestrator at run time — decomposition is dynamic per request, not hard-coded (FR-7)
**And** `GET /workflows` returns only Workflows in the caller's Tenant (RLS enforced)
**And** `GET /workflows/{id}` returns the Workflow record; cross-Tenant returns `404` (no leak)
**When** the user navigates to `/workflows`
**Then** the list page shows all Workflows in the Tenant with name, owner, run count, last-run timestamp, status pill if currently running
**And** the list supports text search and filter by owner
**When** the user opens `/workflows/$id`
**Then** the Definition tab is the default view with: Name (required), Description (textarea, required), Constraints (chip-list editor — optional list of "must check X" statements)
**And** the form follows UX-DR8 (labels above inputs, required marked, inline validation on blur)
**And** navigating with unsaved changes triggers a confirmation dialog
**And** every CRUD operation emits `audit.log()` with `type: "workflow.created" | "workflow.updated"` (FR-21)

### Story 3.2: Workflow Run Lifecycle & State Machine

As a **backend developer building the Orchestrator**,
I want **persisted state machines for `workflow_runs` and `tasks` with compare-and-set transitions**,
So that **Runs are resumable after restart and concurrent workers never double-pick the same Run or Task**.

**Acceptance Criteria:**

**Given** the `workflow_runs` and `tasks` tables exist with `status` enum columns
**When** a User posts `POST /workflows/{id}/runs` with an optional input payload
**Then** a new `workflow_runs` row is created with `status: 'pending'`, `tenant_id`, `workflow_id`, `input`, `created_at`
**And** an arq job is enqueued with materialized `tenant_id` (AD-10) to execute the Run
**When** the arq worker dequeues the job
**Then** it issues `UPDATE workflow_runs SET status='running' WHERE id=? AND status='pending'` and checks `rowcount == 1`
**And** if `rowcount == 0`, the worker abandons (another worker won the race) per AD-6
**When** a state transition is attempted
**Then** every transition is a single `UPDATE ... WHERE id=? AND status=?` with the application checking `rowcount == 1` (AD-6)
**And** the `workflow_runs.status` enum is `pending | running | awaiting_human | completed | failed | timed_out`
**And** the `tasks.status` enum is `pending | claimed | completed | failed`
**When** the arq worker polls `pending` Runs on startup
**Then** Runs that were `running` when the process crashed are safely resumed (RLS session var set from materialized tenant_id)
**And** all state transitions emit `audit.log()` entries with `type: "workflow_run.transition"`, `input: {from, to}`, `output: {rowcount}`
**And** a test verifies two concurrent workers cannot both transition the same Run from `pending` to `running`

### Story 3.3: Orchestrator Decomposition

As a **backend developer**,
I want **the Orchestrator to read a Workflow request and produce Tasks conforming to the Task Schema**,
So that **the right Specialist Agents are dispatched with structured inputs**.

**Acceptance Criteria:**

**Given** a Workflow Run is in `running` state and the Workflow has a description
**When** the Orchestrator (an LLM-driven coordinator) reads the request via `LlmPort.complete(...)` (Story 1.6)
**Then** the Orchestrator produces a set of Tasks, each conforming to the Task Schema `{task, input, output, expected, criteria}` (PRD §A1)
**And** every emitted Task validates against the schema-meta-schema; invalid Tasks are dropped and logged with `type: "task.dropped_invalid"` (FR-8)
**And** each Task names a target Agent by `id` — an unknown or wrong-Department target is rejected before dispatch and logged with `type: "task.routing_rejected"`
**When** the Orchestrator routes Tasks
**Then** routing considers the Agent's Department and declared capabilities (from Agent record)
**And** routing rationale is logged to `audit_trail` with `type: "orchestrator.decomposed"`, `input: {request, workflow_description}`, `output: {tasks: [...], routing_rationale}` (FR-8)
**And** the decomposition is reproducible — the same request + Workflow + Agent set produces a similar Task graph (deterministic enough for audit comparison)
**And** the Orchestrator itself runs via `LlmPort` so its model is configurable (FR-26)
**And** a Task emitted without a valid target Agent is queued for Orchestrator re-decomposition or surfaced as escalation (FR-10)

### Story 3.4: Task Dispatch, Claim & Aggregation

As a **backend developer**,
I want **Tasks dispatched internally via the `tasks` table, claimed by Specialist Agent workers via compare-and-set, with aggregation producing a single Run result**,
So that **the Workflow produces a consolidated answer without coupling to MCP for Task transport**.

**Acceptance Criteria:**

**Given** Tasks are written to the `tasks` table with `status: 'pending'` (Story 3.3)
**When** a Specialist Agent worker polls for pending Tasks targeting its Agent
**Then** it issues `UPDATE tasks SET status='claimed', claimed_at=NOW() WHERE id=? AND status='pending'` and checks `rowcount == 1` (AD-6)
**And** if `rowcount == 0`, another Agent worker won the claim — abandon and pick the next
**When** the Specialist Agent worker completes the Task
**Then** it writes the result to `tasks.result` and transitions `status: 'completed'` (or `'failed'` on error) via compare-and-set
**And** the Specialist Agent may invoke Tools via `McpClientPort` and retrieve KB passages via `kb_search` (Story 2.5) during execution
**When** a Task exceeds 60s without completion
**Then** the Task is transitioned to `failed` with reason `timeout`
**And** the dispatch is retried up to 2 times with exponential backoff (e.g., 2s, 8s) before final failure (FR-9)
**When** all expected Task responses are received OR the 60s/Agent timeout fires
**Then** the Orchestrator aggregates all responses into a single Workflow Run result
**And** aggregation logic (which responses merged, which dropped) is logged to `audit_trail` with `type: "orchestrator.aggregated"` (FR-9)
**And** the Run transitions to `completed` (or `failed` if all Tasks failed) via compare-and-set
**And** a test verifies that no Task is double-claimed by concurrent Specialist Agent workers

### Story 3.5: Per-Step Feedback Incorporation

As a **Specialist Agent**,
I want **to attach structured confidence feedback to my responses**,
So that **the Orchestrator can decide whether to aggregate, escalate, or request a follow-up Task**.

**Acceptance Criteria:**

**Given** a Specialist Agent completes a Task (Story 3.4)
**When** the Agent writes its result to `tasks.result`
**Then** the result includes a structured feedback object: `{confidence: float 0–1, flags: enum[], rationale: text}` (FR-11)
**And** the `flags` enum includes values like `requires_human_validation`, `policy_conflict`, `missing_information`, `cross_department_dependency`
**When** the Orchestrator aggregates responses
**Then** it consumes each Task's feedback to decide:
- aggregate normally if all confidence ≥ threshold (default 0.7) and no escalation flags
- escalate to human if any Task has `requires_human_validation` or `policy_conflict` flag (FR-10)
- request a follow-up Task from another Agent if `missing_information` flag and confidence allows
**And** the consumption decision is logged to `audit_trail` with `type: "orchestrator.feedback_consumed"`, `input: {task_id, feedback}`, `output: {decision: "aggregated" | "escalated" | "followup", reason}`
**And** feedback is structured — never free-form text — so the Orchestrator can reason over it deterministically
**And** the confidence threshold is configurable per Workflow (not hard-coded)

### Story 3.6: Human-in-the-Loop Escalation

As a **user with operator or manager role**,
I want **to be notified when a Workflow Run escalates and to resolve it with my decision recorded**,
So that **banking decisions with conflict or low confidence get human oversight before completion**.

**Acceptance Criteria:**

**Given** the Orchestrator detects a conflict between Agent responses, low aggregation confidence, or an explicit `requires_human_validation` flag (Story 3.5)
**When** the Orchestrator decides to escalate
**Then** it emits an escalation event `{run_id, conflicting_steps: [task_ids], suggested_resolutions: [...], rationale}` (FR-10)
**And** it transitions the Run from `running` to `awaiting_human` via compare-and-set (AD-6)
**And** the escalation appears in the global Escalation Inbox (topbar bell count increments)
**When** the User opens the Run View (Story 3.8) for an `awaiting_human` Run
**Then** the escalation panel shows: current status, per-step feedback from each Agent, the conflicting responses side-by-side, suggested resolutions, and decision affordances: Resolve / Override / Reject
**When** the User submits a resolution
**Then** the resolution is recorded with `user_id`, `timestamp`, `rationale`, and `decision` enum (`resolved`, `overridden`, `rejected`)
**And** the resumed Run inherits the resolution and transitions back to `running` (or `completed` if the resolution ends the Run)
**When** a Run is `awaiting_human` for more than 5 minutes
**Then** it transitions to `timed_out` and surfaces in the Trace Dashboard as a timeout event (FR-10)
**And** the timeout is configurable per Workflow
**And** the entire escalation lifecycle is logged to `audit_trail` with `type: "escalation.created"`, `"escalation.resolved"`, `"escalation.timed_out"`
**And** a test verifies that a Run cannot transition out of `awaiting_human` without either a resolution or a timeout

### Story 3.7: Workflow Runs List UI

As a **user**,
I want **to see all Runs for a Workflow with their current status**,
So that **I can monitor ongoing work and review history**.

**Acceptance Criteria:**

**Given** the Run endpoints from Story 3.2
**When** the user navigates to `/workflows/$id/runs`
**Then** a list of Runs for the Workflow renders, each row showing: Run ID (truncated), status pill (UX-DR11), started-at, duration, triggered-by (user/schedule/event), escalation indicator
**And** the list supports filtering by status (multi-select: pending, running, awaiting_human, completed, failed, timed_out) and time range (last hour, last day, last week, custom)
**And** the list supports sorting by started-at (default desc) and duration
**And** pagination handles Runs > 50 with cursor-based pagination (meta per AR-14)
**When** a Run is currently `running` or `awaiting_human`
**Then** its row shows a live-updating status pill (polling at 1s interval) without manual refresh
**And** an empty state renders when the Workflow has zero Runs (UX-DR23: "No runs yet. Click Run to start.")
**And** clicking a row navigates to the Run View (Story 3.8)
**And** the global "Run" split-button in the topbar starts a new Run for this Workflow with an optional input payload modal

### Story 3.8: Live Run View with Escalation Panel

As a **user watching a Run unfold**,
I want **a live view of the Run's Task graph, current statuses, and any escalations requiring my input**,
So that **I can observe multi-agent collaboration in real time and intervene when needed**.

**Acceptance Criteria:**

**Given** the Run endpoints from Stories 3.2 through 3.6
**When** the user opens `/workflows/$id/runs/$runId`
**Then** the Run View renders three sections: Header (Run ID, status pill, started-at, duration counter, trigger source), Task Stream (cards appearing as Tasks are dispatched/claimed/completed), and Escalation Panel (visible only when `status == 'awaiting_human'`)
**And** the Task Stream polls for updates at 1s intervals (NFR-1: first-response <5s p95) and renders new Task cards with the trace-step animation (UX-DR9: 180ms fade + 4px slide-up, interruptible)
**And** each Task card shows: target Agent name + Department badge, Task type, status pill, latency, expand-for-detail affordance (click to expand input/output)
**When** the Run is `awaiting_human`
**Then** the Escalation Panel renders prominently (per Story 3.6): conflicting responses side-by-side, per-step feedback, suggested resolutions, and Resolve/Override/Reject buttons
**And** submitting a resolution fires `POST /runs/{id}/resolve` and the Run transitions visibly (no full page reload)
**When** the Run completes or fails
**Then** the final aggregated result renders in a result panel with a "View in Trace Dashboard" link (Epic 6)
**And** the `aria-live="polite"` region announces status transitions for screen readers (UX-DR12); `aria-live="assertive"` for errors
**And** a shareable URL allows opening the same Run View directly (deep link)
**And** the page degrades gracefully if polling fails — shows a "reconnecting" indicator with retry

---

## Epic 4: Mini-App Builder & Visibility Tier Enforcement

A Specialist Agent (or the Orchestrator) can emit an entity schema and have the platform auto-provision a fully-functional Mini-App — JSONB namespace, CRUD endpoints, auth-gated React UI, and App Event emission — all gated by row-level Visibility Tier rules.

### Story 4.1: Mini-App Schema Emission & Validation

As a **Specialist Agent or the Orchestrator**,
I want **to emit a JSON entity schema plus UI spec describing a Mini-App**,
So that **the platform can provision a working Mini-App without manual setup**.

**Acceptance Criteria:**

**Given** an Agent or the Orchestrator completes a Task that should produce a Mini-App
**When** it emits a JSON document containing `{entity_schema: {fields, types, validations}, ui_spec: {layout, components, primary_actions}, visibility_tier, initial_rows?}`
**Then** the emission is validated against the platform's schema-meta-schema before any persistence (FR-12)
**And** the schema-meta-schema enforces: field names are snake_case, types are one of `{string, number, boolean, datetime, json, reference}`, validations are JSON Schema constraints, ui_spec components are from an allowed set (input, textarea, select, checkbox, date, table, card, button)
**When** the emission fails validation
**Then** it is rejected with a structured error and logged to `audit_trail` with `type: "mini_app.emission_rejected"`, `input: {agent_id, prompt, errors}` (FR-12)
**When** the emission is valid
**Then** it is captured in `audit_trail` with `type: "mini_app.emitted"`, `input: {agent_id, prompt}`, `output: {schema_hash, field_count, ui_component_count}` (FR-12)
**And** the emission carries the originating Agent's `tenant_id` and `department_id` automatically (never user-supplied — derived from context)

### Story 4.2: Atomic Mini-App Provisioning (Namespace + CRUD + UI)

As a **backend developer**,
I want **the Provisioner to atomically create the namespace, endpoints, and UI shell in one transaction**,
So that **a Mini-App is either fully provisioned or not at all — no partial states**.

**Acceptance Criteria:**

**Given** a valid Mini-App emission from Story 4.1
**When** the Provisioner function `provision(tenant_id, department_id, owner_id, valid_schema, initial_rows?)` is called
**Then** it creates in **one DB transaction** (AD-8):
- a new `mini_apps` row with UUID v7 `app_id`, `tenant_id`, `department_id`, `owner_id`, `visibility_tier`, `schema` (JSONB), `ui_spec` (JSONB), `created_at`
- the `mini_app_rows` namespace (rows will carry `tenant_id`, `department_id`, `owner_id`, `visibility_tier`, `version`, plus schema-defined fields stored as JSONB)
- the auto-generated CRUD endpoint route registration (Story 4.4)
- the React UI route registration (Story 4.5)
**And** if any step fails, the entire transaction rolls back — no partial Mini-App exists
**When** the transaction commits
**Then** the new Mini-App gets a unique `app_id` and a writeable namespace within 2s of emission (FR-13)
**And** any `initial_rows` from the emission are inserted as the first rows in the namespace, each carrying the four access fields (`tenant_id`, `department_id`, `owner_id`, `visibility_tier`); none can be null (FR-13)
**And** per-tenant data isolation is enforced at the data layer (RLS from Story 1.2 applies to `mini_apps` and `mini_app_rows`)
**And** the Provisioner is a pure function — no side effects outside the transaction (AD-8)
**And** provisioning emits `audit.log()` with `type: "mini_app.provisioned"`, `output: {app_id, row_count, endpoint_count}`

### Story 4.3: Visibility Tier RLS Enforcement on `mini_app_rows`

As a **backend developer**,
I want **Visibility Tier (`Public` / `Need-Auth` / `Private`) enforced at the row level via Postgres RLS**,
So that **no API path — including auto-generated CRUD and future bulk imports — can bypass the access matrix**.

**Acceptance Criteria:**

**Given** the `mini_app_rows` table with columns `tenant_id`, `department_id`, `owner_id`, `visibility_tier`, `version`, plus per-Mini-App JSONB fields
**When** a Postgres RLS policy is evaluated for a row read
**Then** the policy encodes the access matrix (PRD §A3) using `visibility_tier`, `department_id`, and a whitelist check:
- `Public`: any User in the same Tenant can read
- `Need-Auth`: any User in the same Tenant AND same Department can read
- `Private`: only Users in the whitelist (per-row `whitelist_user_ids` JSONB field) can read
**When** an anonymous request attempts to read a `Need-Auth` Mini-App
**Then** the response is `401` with `code: "UNAUTHENTICATED"` (FR-16)
**When** a same-Tenant, wrong-Department request attempts to read a `Need-Auth` Mini-App
**Then** the response is `403` with `code: "FORBIDDEN"` (FR-16)
**When** a non-whitelisted same-Department request attempts to read a `Private` Mini-App
**Then** the response is `403` with `code: "FORBIDDEN"` (FR-16)
**And** the RLS policies are applied at the DB layer, not the API layer — direct SQL inspection confirms row-level filtering (AD-5)
**And** writes follow the same rules (a User cannot create a row in a Mini-App they cannot read)
**And** the `version` column supports optimistic concurrency (AD-6) — every UPDATE bumps `version` and a stale-version write is rejected with `409 Conflict`

### Story 4.4: Auto-Generated CRUD Endpoints

As a **user or external system**,
I want **each Mini-App to expose CRUD endpoints generated from its entity schema**,
So that **I can create, read, update, and delete rows in the Mini-App's namespace**.

**Acceptance Criteria:**

**Given** a Mini-App was provisioned (Story 4.2)
**When** the route registration runs
**Then** the following endpoints exist within 2s of namespace provisioning (FR-14):
- `POST /mini-apps/{app_id}/rows` — create a new row
- `GET /mini-apps/{app_id}/rows` — list rows with pagination
- `GET /mini-apps/{app_id}/rows/{row_id}` — get one row
- `PATCH /mini-apps/{app_id}/rows/{row_id}` — update a row (requires `version` for optimistic concurrency)
- `DELETE /mini-apps/{app_id}/rows/{row_id}` — soft-delete a row
**And** every endpoint validates input against the entity schema (Story 4.1) and rejects with `422` on schema violation
**And** every endpoint is gated by RLS (Story 4.3) — `Public`/`Need-Auth`/`Private` enforced server-side
**When** a `Private` Mini-App rejects a non-whitelisted User
**Then** the response is `403` with `code: "FORBIDDEN"` (FR-14)
**And** every write triggers App Event emission (Story 4.6) via the CRUD endpoint, not from Agent code (AD-8: mini_app module is sole writer post-provisioning)
**And** list responses follow the standard envelope `{data: [rows], error: null, meta: {pagination: {total, page, limit}}}` (AR-14)
**And** every CRUD operation emits `audit.log()` with `type: "mini_app.row.created" | "updated" | "deleted"`

### Story 4.5: Auto-Generated Auth-Gated React UI

As a **user**,
I want **each Mini-App to have a React UI rendered from its UI spec**,
So that **I can interact with the Mini-App's data without writing custom frontend code**.

**Acceptance Criteria:**

**Given** a Mini-App was provisioned (Story 4.2) with a valid `ui_spec`
**When** the route registration creates the UI route
**Then** the UI is reachable at `/mini-apps/$appId` within 5s of endpoint generation (FR-15)
**And** the UI is rendered at runtime from the UI spec — no build step per Mini-App (JSON-spec → React component tree)
**And** the UI spec's `{layout, components, primary_actions}` drives the layout: e.g., a `table` component renders rows in a sortable table, a `card` component renders rows as cards, `primary_actions` become buttons in a header
**And** the UI calls the auto-generated CRUD endpoints (Story 4.4) — never bypasses them (FR-15)
**When** an unauthenticated User visits `/mini-apps/$appId` for a `Need-Auth` or `Private` Mini-App
**Then** they are redirected to login (no client-only gating — server returns 401, client reacts)
**When** an authenticated but unauthorized User visits
**Then** the UI shows an "Access Denied" state with the underlying 403 reason
**And** row creates, edits, and deletes via the UI flow through PATCH/POST/DELETE endpoints and reflect immediately in the JSONB namespace
**And** optimistic concurrency is handled — if a stale `version` write fails with `409`, the UI shows a conflict dialog and refreshes the row
**And** the UI uses the design system primitives from Story 1.9 (buttons, tables, forms, status pills)

### Story 4.6: App Event Emission to Action Bus

As a **Mini-App row changes**,
I want **structured App Events emitted onto the Action Bus**,
So that **Event Triggers (Epic 5) and subscribed Workflow Runs can react to Mini-App activity**.

**Acceptance Criteria:**

**Given** a Mini-App's CRUD endpoint performs a row change (create/update/delete) (Story 4.4)
**When** the change commits
**Then** the CRUD endpoint (not Agent code — AD-8, AD-9) emits an App Event onto the arq Action Bus with envelope: `{app_id, tenant_id, department_id, actor_user_id, event_type, payload, timestamp, sequence_number}` (FR-17, PRD §A5)
**And** `event_type` follows `domain.event_type` convention: `mini_app.row.created`, `mini_app.row.updated`, `mini_app.row.deleted` (AR-14)
**And** `payload` contains the row delta (for update) or full row (for create/delete)
**And** the App Event appears on the Action Bus within 1s of the row change (FR-17)
**And** sequence numbers are per-`app_id` (monotonically increasing within an app)
**When** a Workflow Run has an Event Trigger subscribed to this App Event
**Then** the App Event is visible in that Run's audit trail via the Event Trigger match (FR-17)
**When** an App Event is lost (e.g., worker crash before ack)
**Then** the loss is detectable through a sequence-number gap (e.g., seq 5 → seq 7 with no seq 6) visible in the Trace Dashboard (Epic 6)
**And** the Action Bus delivers App Events at-least-once (FR-20, full Epic 5)
**And** every emission is logged to `audit_trail` with `type: "app_event.emitted"`, `output: {app_id, event_type, sequence_number}`
**And** the actor's auth header / PII is never in the payload (NFR-9)

### Story 4.7: Mini-App Catalog UI

As a **user**,
I want **to see all Mini-Apps in my Tenant**,
So that **I can navigate to a specific Mini-App or see what's been generated**.

**Acceptance Criteria:**

**Given** the Mini-App list endpoint exists
**When** the user navigates to `/mini-apps`
**Then** the catalog renders as a grid of cards, each showing: app name (derived from schema or first prompt), owning Department badge, Visibility Tier badge (Public/Need-Auth/Private), row count, last activity timestamp, status pill (Active)
**And** the catalog supports filtering by Department and Visibility Tier
**And** the catalog supports text search on app name
**When** a User clicks a Mini-App card
**Then** they navigate to `/mini-apps/$appId` (Story 4.5) — if unauthorized, the redirect/error path applies
**When** the User has access to zero Mini-Apps
**Then** an empty state renders (UX-DR23): "No Mini-Apps yet. Run a Workflow that emits a schema to generate one."
**And** the catalog uses the design system's card component (UX-DR5)
**And** each card's "last activity" updates via polling (1s interval) when activity is recent (< 5 minutes ago)

### Story 4.8: Generated Mini-App View with Live Event Stream

As a **user interacting with a Mini-App**,
I want **the auto-generated UI plus a live stream of App Events**,
So that **I can see data changes as they happen and understand cause-and-effect**.

**Acceptance Criteria:**

**Given** the user is authorized to view a Mini-App (Story 4.5)
**When** they open `/mini-apps/$appId`
**Then** the layout renders two panels: main content (auto-generated UI from Story 4.5) and a right-side live event stream (UX-DR19)
**And** the event stream shows the last 20 App Events for this `app_id`, each entry showing: timestamp, event_type, actor, row ID, delta summary
**And** new events appear at the top of the stream in real time (1s polling) with the trace-step animation (UX-DR9: 180ms fade + slide-up, interruptible)
**When** the user clicks an event in the stream
**Then** the corresponding row in the main UI highlights briefly (causality cue)
**When** the Mini-App has Visibility Tier `Private` and the whitelist changes
**Then** the UI gracefully handles losing access (shows "Access revoked" state, no error flash)
**And** the event stream filterable by event_type via chips at the top (created/updated/deleted)
**And** the event stream is collapsible (icon button top-right) to give the main UI more space
**And** an `aria-live="polite"` region announces new events for screen readers (UX-DR12)

---

## Epic 5: Actions, Triggers & Event-Driven Automation

A user can register Schedule Triggers (cron) and Event Triggers (App Event matches) so that follow-on Workflows fire automatically — closing the loop.

### Story 5.1: Schedule Trigger Registration & Cron Execution

As a **user with builder role**,
I want **to register Schedule Triggers that fire Workflow Runs on a cron schedule**,
So that **recurring banking workflows happen automatically without manual kickoff**.

**Acceptance Criteria:**

**Given** an authenticated User with builder role and an existing Workflow
**When** the User posts `POST /triggers/schedule` with `{workflow_id, cron_expression, input_payload?, enabled: true}`
**Then** the response is `201` with `trigger_id` (UUID v7), `tenant_id`, `department_id`, `next_fire_at`
**And** the `cron_expression` follows standard 5-field syntax (minute hour day month day-of-week); invalid expressions return `422` with details
**When** the arq `cron_jobs` entrypoint fires
**Then** it runs under `BYPASSRLS`, enumerates all Tenants with matching schedules, and enqueues one per-Tenant Run job with materialized `tenant_id` for each (AD-10)
**And** the per-Tenant Run job sets the tenant contextvar at worker entry before any domain work (AD-10)
**And** a Schedule Trigger fires within 60s of its scheduled time (FR-18, NFR assumption)
**And** each firing creates a Workflow Run visible in the Trace Dashboard with `trigger_source: "schedule"` (FR-18)
**And** the Schedule Trigger is tenant-scoped — TenantA's schedule never fires TenantB's Workflow
**And** every fire emits `audit.log()` with `type: "action.trigger.fired"`, `input: {trigger_id, scheduled_at, fired_at, tenant_id}`
**And** the trigger supports enable/disable without deletion (`PATCH /triggers/schedule/{id}` with `enabled: false`)

### Story 5.2: Event Trigger Registration & Matching

As a **user with builder role**,
I want **to register Event Triggers that fire Workflow Runs when matching App Events land on the Action Bus**,
So that **the closed loop completes — Mini-App changes drive follow-on automation**.

**Acceptance Criteria:**

**Given** an authenticated User with builder role and an existing Workflow
**When** the User posts `POST /triggers/event` with `{workflow_id, filter: {app_id, event_type, predicate?}, input_template?, enabled: true}`
**Then** the response is `201` with `trigger_id`, `tenant_id`, `department_id`
**And** the filter declares `app_id` (target Mini-App), `event_type` (e.g., `mini_app.row.created`), and optional JSON-path predicate on payload (e.g., `$.field.loan_amount > 100000`)
**When** an App Event lands on the Action Bus (Story 4.6)
**Then** the Event Trigger matcher evaluates all enabled Event Triggers in the same Tenant against the event
**And** matching events (app_id + event_type + predicate passes) fire a Workflow Run within 5s (FR-19)
**And** non-matching events do not fire any Run
**And** the fired Run's `input` is hydrated from the App Event payload + the trigger's `input_template`
**And** the Run's `trigger_source` is `"event"` and the triggering `app_event_id` is recorded for traceability
**And** the matcher is tenant-scoped — TenantA's trigger never matches TenantB's events
**And** every match emits `audit.log()` with `type: "action.trigger.matched"`, `input: {trigger_id, app_event_id, workflow_id}`
**And** non-matching evaluations do not log (avoid spam) but a daily summary count is available

### Story 5.3: Action Bus Reliability & Sequence Numbers

As a **backend developer**,
I want **the Action Bus to guarantee at-least-once delivery with sequence numbers for gap detection**,
So that **subscribers can resume after crashes and auditors can spot missing events**.

**Acceptance Criteria:**

**Given** the Action Bus is an arq queue (Redis 7.4+ backed)
**When** a subscriber (Event Trigger matcher or Workflow Run) consumes an App Event
**Then** it acks the message only after successful processing
**And** if the subscriber crashes before acking, the message is redelivered (at-least-once — FR-20)
**When** a subscriber restarts
**Then** it resumes from the last-acked sequence number per `app_id` (FR-20)
**And** the per-`app_id` sequence number is monotonically increasing
**When** a sequence-number gap is detected (e.g., the subscriber sees seq 7 after seq 5 with no seq 6)
**Then** the gap is logged to `audit_trail` with `type: "action_bus.gap_detected"`, `input: {app_id, expected_seq, actual_seq}`
**And** the gap is surfaced in the Trace Dashboard (Epic 6) for diagnosis
**And** redelivery does not produce duplicate Workflow Runs for the same event — the Event Trigger matcher is idempotent (checks `app_event_id` against recently-fired Runs)
**And** a test verifies that a subscriber crash mid-processing does not lose events
**And** out-of-scope for MVP: exactly-once semantics, cross-Tenant event fanout, event replay UI (FR-20 non-goals)

### Story 5.4: Actions Surface UI

As a **user managing triggers**,
I want **a single surface to create and manage Schedule and Event Triggers**,
So that **I can configure automation without hunting through menus**.

**Acceptance Criteria:**

**Given** the trigger endpoints from Stories 5.1 and 5.2
**When** the user navigates to `/actions`
**Then** the page shows two tabs: "Schedule Triggers" and "Event Triggers" (UX-DR20)
**And** each tab shows a list of triggers with: name (derived from workflow + schedule/filter), target Workflow link, status (Enabled/Disabled), last-fired timestamp, next-fire (for Schedule)
**And** each tab has a "New Trigger" button opening a creation form
**When** the user opens the Schedule Trigger form
**Then** it includes: Workflow picker (select from caller's Tenant Workflows), Cron Expression (text input + visual builder helper showing human-readable preview like "Every weekday at 09:00"), Input Payload (optional JSON editor), Enabled toggle
**And** the form validates the cron expression client-side and shows the next-fire preview
**When** the user opens the Event Trigger form
**Then** it includes: Workflow picker, Mini-App picker (select from caller's Tenant Mini-Apps), Event Type (select: `mini_app.row.created/updated/deleted`), JSON-Path Predicate (optional, monaco-editor), Input Template (optional), Enabled toggle
**And** the form validates the JSON-path predicate against sample payloads
**When** the user toggles a trigger's enabled state from the list
**Then** a `PATCH /triggers/{type}/{id}` fires and the list updates optimistically
**And** a trigger's row click opens an edit form (full lifecycle: edit, disable, delete with confirmation)
**And** the page follows UX-DR23 for empty/loading/error states
**And** keyboard navigation works across tabs and forms (UX-DR12)

### Story 5.5: Trigger Lifecycle & Audit History

As a **user**,
I want **to see the history of trigger fires and manage trigger lifecycle**,
So that **I can verify triggers are firing correctly and clean up stale ones**.

**Acceptance Criteria:**

**Given** triggers exist and have fired
**When** the user opens a trigger's detail view
**Then** the detail shows: trigger configuration, enabled state, last 20 fires (timestamp, target Run ID with link to Trace, status), and lifecycle actions
**And** lifecycle actions include: Edit, Disable/Enable, Delete (with confirmation dialog — destructive action per UX-DR3)
**When** the user deletes a trigger
**Then** a soft-delete marks the trigger as `deleted_at = NOW()` (preserves audit referential integrity)
**And** no new fires occur after deletion
**And** the trigger disappears from the list (filtered out)
**And** every lifecycle action emits `audit.log()` with `type: "trigger.created" | "updated" | "deleted"`
**When** a trigger has not fired in 30 days
**Then** the list shows a "stale" indicator on the row (informational)
**And** the detail view's fire history supports filtering by status (success/failed) and time range
**And** clicking a fire entry's Run ID navigates to the Run View in Epic 3

---

## Epic 6: Trace Dashboard & Audit Provenance

A judge or auditor can open any Workflow Run, switch between timeline and collaboration-graph views of the same Audit Trail, expand any step for full input/output detail, and export a signed JSON audit package.

### Story 6.1: Trace Dashboard Timeline View

As a **judge or auditor**,
I want **to view a Workflow Run's Audit Trail as a vertical timeline**,
So that **I can trace the decision sequence step-by-step**.

**Acceptance Criteria:**

**Given** the `audit_trail` table contains entries for a Run (FR-21, written throughout Epics 1–5)
**When** the user navigates to `/audit/$runId` (or clicks "View in Trace Dashboard" from the Run View)
**Then** the timeline view renders by default — a vertical sequence of cards, each card showing: step type (icon + label), agent name (or "Orchestrator"), latency, status pill (UX-DR11), timestamp
**And** each card has an expand-for-detail affordance — click to expand input, output, and the raw audit entry JSON (UX-DR22 referenced)
**And** a Run with 20+ steps renders in under 1s on the demo laptop (FR-22, NFR-3)
**When** a Run has more than 1,000 entries
**Then** the timeline virtualizes (TanStack virtual) to maintain <1s render
**And** the timeline supports scroll-to-step via a mini-map (right-side bar showing step density)
**When** the user clicks a card to expand
**Then** the input/output renders in code blocks with copy button and syntax highlighting (UX-DR7)
**And** long fields are truncated with "show more" affordance to keep the card readable
**And** the timeline is shareable by URL within the Tenant (deep link preserves Run selection and scroll position)
**And** an `aria-live="polite"` region announces step count for screen readers

### Story 6.2: Trace Dashboard Collaboration Graph View

As a **judge**,
I want **the same Audit Trail rendered as a graph showing Orchestrator-Agent collaboration**,
So that **I can understand multi-agent coordination at a glance**.

**Acceptance Criteria:**

**Given** the timeline view from Story 6.1 is rendered
**When** the user clicks the "Graph" toggle (or presses `g` keyboard shortcut)
**Then** the same Audit Trail renders as a collaboration graph: Orchestrator node at the top, Specialist Agent nodes below (one per unique Agent invoked), edges labelled with Task type and status (FR-23)
**And** the graph renders in under 1s for any Run with ≤ 10 Specialist Agent invocations (FR-23)
**And** the graph uses ReactFlow with restrained motion (UX-DR9)
**When** the user clicks a node
**Then** the corresponding Audit Trail entries filter the timeline (clicking Agent node X shows only X's entries in the timeline view if user toggles back)
**And** clicking an edge shows the Task dispatch detail (input/output)
**And** the graph and the timeline are alternate views of the same underlying Audit Trail — toggling preserves scroll/selection context (FR-23)
**When** a Run has more than 10 Specialist Agent invocations
**Then** the graph shows a "Graph view optimal for ≤10 agents; showing first 10 + collapsed remainder" notice with a "Show all" override
**And** the graph exports as PNG/SVG via a download button (for inclusion in audit reports)
**And** node positions are stable across re-renders (deterministic layout) so screenshots are reproducible

### Story 6.3: Audit Trail Explorer

As a **compliance officer**,
I want **a tenant-wide Audit Trail explorer with filters**,
So that **I can investigate patterns across Runs without opening each one individually**.

**Acceptance Criteria:**

**Given** the user has manager or operator role
**When** they navigate to `/audit`
**Then** the Audit Trail Explorer renders as a table (UX-DR6): columns include `run_id`, `step_id`, `agent_id`, `timestamp`, `type`, `latency_ms`, `model`
**And** the table supports filters: `run_id` (multi-select), `agent_id` (multi-select), `type` (multi-select enum), time range (last hour/day/week/custom)
**And** the table supports sorting by any column
**And** pagination is cursor-based (AR-14 envelope meta) handling > 10,000 entries
**When** the user clicks a row
**Then** a detail panel (UX-DR13 inspector, 320px right) opens with the full entry: input JSON, output JSON, model metadata, latency breakdown
**And** the detail panel includes a "Open in Run Trace" link to navigate to `/audit/$runId` with the entry pre-selected
**When** the user applies filters that return zero entries
**Then** an empty state renders (UX-DR23)
**And** the filter state is reflected in the URL (shareable queries)
**And** the table header is sticky for long scrolls (UX-DR6)
**And** performance: list endpoint returns paginated results in under 500ms for any filter combination

### Story 6.4: Audit Export (Signed JSON)

As a **compliance officer preparing an audit package**,
I want **to export a Run's Audit Trail as a signed JSON document**,
So that **the package is tamper-evident and machine-readable for downstream audit review**.

**Acceptance Criteria:**

**Given** the user is viewing a Run Trace (Story 6.1 or 6.2)
**When** they click "Export Audit" in the header
**Then** a `GET /runs/{run_id}/audit-export` request fires
**And** the response is a downloadable JSON file containing every audit entry for the Run, signed with the Tenant's audit key (FR-24)
**And** the signature is an Ed25519 detached signature in a `.sig` companion file (or embedded per-entry — implementation choice)
**And** the export completes within 5s for any Run with ≤ 1,000 entries (FR-24)
**When** the export is generated
**Then** the JSON envelope contains: `{run_id, tenant_id, exported_at, entry_count, signature_algorithm, entries: [...]}`
**And** every entry includes the full FR-21 schema: `{run_id, step_id, agent_id, ts, type, input, output, latency_ms, model}`
**And** the audit key is stored encrypted at rest (per AR-14) and never appears in the export
**When** an entry contains data marked PII-safe by the originating Agent (FR NFR-9)
**Then** the entry is included as-is; entries that should not be exported (e.g., revoked PII) are filtered with a redaction notice
**And** every export emits `audit.log()` with `type: "audit.exported"`, `output: {run_id, entry_count, signature_algorithm, exported_by_user_id}`
**And** a test verifies the signature validates against the Tenant's public audit key

### Story 6.5: Mobile Read-Only Fallback

As a **user on a mobile device**,
I want **a read-only view of Run status and escalation response**,
So that **I can monitor and intervene from my phone without full desktop layout**.

**Acceptance Criteria:**

**Given** the user opens VAIC on a viewport < 768px
**When** any primary surface is accessed
**Then** the layout switches to a single-column read-only mode (UX-DR24)
**And** only two surfaces are interactive on mobile: Run status list and Escalation response
**When** the user views a Run on mobile
**Then** they see: Run name, status pill, started-at, current step summary, escalation indicator (if `awaiting_human`)
**And** if the Run is `awaiting_human`, the escalation panel renders with Resolve/Override/Reject buttons (same as desktop Story 3.8)
**And** no Mini-App editing, no Agent configuration, no Trigger management on mobile — these show a "Desktop required" state
**And** the mobile layout uses the same design tokens but simplified spacing (16px page padding)
**And** touch targets are minimum 44×44px (UX-DR12)
**And** the mobile view respects `prefers-color-scheme` (dark mode)
**And** performance: mobile page load < 2s on 4G (NFR-2 spirit)

### Story 6.6: Chart & Graph Accessibility

As a **user relying on assistive technology**,
I want **every chart and graph to have a table alternative**,
So that **I can access the same data without relying on visual rendering**.

**Acceptance Criteria:**

**Given** the Trace Dashboard has rendered the collaboration graph (Story 6.2) or any chart
**When** the user tabs through the surface
**Then** every chart has an accessible table alternative reachable by tab (UX-DR12)
**And** the table contains the same data as the visual chart (no information loss)
**When** the collaboration graph is rendered
**Then** an adjacency list panel renders below or beside the graph showing: each node, its connections, edge labels
**And** the adjacency list is keyboard-navigable (Tab/Shift+Tab, arrow keys within)
**When** the user activates a "Table view" toggle on any chart
**Then** the visual chart is replaced by the accessible table view, preserving the same data
**And** both views are kept in sync — filtering in one filters the other
**And** the table views use the standard Table component (UX-DR6) with sticky headers and sortable columns
**And** `aria-label`s on charts describe the data they represent (e.g., "Collaboration graph showing 5 Specialist Agents invoked by Orchestrator for Run XYZ")

---

## Epic 7: Integration & Demo Readiness

A judge watches the full closed-loop demo: Linh configures Agent → Workflow Run → Mini-App auto-generated → row edit fires App Event → Event Trigger fires next Run — all visible in the Trace Dashboard. Bootstrap script produces a fresh Tenant in under 60s.

### Story 7.1: Stub-to-Real Implementation Wiring

As a **backend developer completing integration**,
I want **all stubbed ports replaced with real implementations**,
So that **the closed loop runs end-to-end against real data, not canned fixtures**.

**Acceptance Criteria:**

**Given** all parallel epics (2–6) have shipped their real implementations
**When** integration begins
**Then** each stub from Story 1.4 is replaced by its real implementation:
- `AgentProviderPort` stub → Epic 2 `agent_builder.service`
- `WorkflowRunPort` stub → Epic 3 `orchestrator.service`
- `MiniAppProvisionerPort` stub → Epic 4 `mini_app.provisioner`
- `TriggerRegistryPort` stub → Epic 5 `actions.triggers`
- `McpClientPort` stub → real MCP client calling the parallel-team MCP server (or its stub if unavailable)
**And** each wiring has an integration test verifying the real path works (not just the contract)
**When** a stub is removed
**Then** no remaining code references the stub (verified by `grep`/import check)
**And** the stubs directory (`core/ports/stubs/`) is preserved for future testing but unused in production paths
**And** every wiring emits an `audit.log()` on first successful call confirming integration (informational)
**And** a "wiring report" document is generated listing which stubs were replaced, when, and by whom (traceability)

### Story 7.2: Closed-Loop End-to-End Test

As a **backend developer validating the closed loop**,
I want **Playwright E2E tests covering UJ-1 and UJ-2**,
So that **the demo can be run repeatedly with confidence that it works**.

**Acceptance Criteria:**

**Given** all real implementations are wired (Story 7.1)
**When** the Playwright test suite runs against a freshly bootstrapped Tenant
**Then** the UJ-1 test (Linh configures end-to-end) verifies: login → create Agent → upload KB doc → register Tool → configure Model → create Workflow → start Run → watch decomposition → resolve escalation (if surfaced) → verify Mini-App generated → edit a Mini-App row → see App Event in stream
**And** the UJ-2 test (Judge watches one flow) verifies: login → open pre-configured Run → toggle timeline/graph views → expand a step → export audit JSON → validate signature
**And** the closed-loop test verifies: Agent emits schema → Mini-App provisioned → user edits row → App Event emitted → Event Trigger fires → next Workflow Run starts → result visible in Trace
**And** all tests use synthetic loan case fixtures (not real customer data — NFR-9)
**When** any step fails
**Then** the test produces a screenshot + trace dump for debugging
**And** tests run in CI on every PR to main
**And** the full closed-loop test completes in under 5 minutes on the demo hardware
**And** the test suite is hermetic — running it twice produces the same outcome (idempotent bootstrap)

### Story 7.3: Full Demo Bootstrap (FR-28)

As a **demo operator preparing for the hackathon**,
I want **a single command to bootstrap a fully-loaded demo Tenant**,
So that **I can reset the demo to a known-good state in under 60s**.

**Acceptance Criteria:**

**Given** the minimal bootstrap from Story 1.12 exists
**When** the operator runs `python scripts/bootstrap_demo_tenant.py --full-demo`
**Then** the script creates (idempotently, under `BYPASSRLS`):
- 1 Tenant "SHB Demo"
- 2 Departments: "Credit", "Operations"
- 3 Users: 1 builder, 1 manager, 1 operator with documented credentials
- 3 Specialist Agents: "Credit Policy Agent" (Credit dept, KB-loaded), "Compliance Agent" (Credit dept, KB-loaded), "Operations Agent" (Operations dept)
- 1 Knowledge Base per Agent with synthetic policy documents (no real PII — NFR-9)
- 1 Workflow: "Business Loan Pre-Screening" with natural-language description and constraints
- 1 Schedule Trigger firing the Workflow on a configurable cron (disabled by default)
- 1 Event Trigger firing a follow-up Workflow on `mini_app.row.created` for the demo Mini-App
- 1 pre-provisioned Mini-App "Loan Cases" with 3 synthetic loan case rows
**And** the script completes in under 60s (FR-28)
**And** the script is idempotent — running it twice does not corrupt data (detects existing entities by name and skips or updates)
**And** the script is NOT a hard-coded demo — the same platform surfaces used to build the pre-configured Workflow are available to the User at run time (FR-28)
**And** the script logs progress with timestamps and a final summary: "Bootstrap complete in Xs — Tenant Y, Z Agents, W Workflows, V Mini-Apps"
**When** the script encounters an error
**Then** it fails fast with a clear error message and exits non-zero
**And** no partial state persists — failed bootstrap rolls back the current entity

### Story 7.4: NFR Validation

As a **tech lead verifying production readiness**,
I want **all NFRs validated against the running system**,
So that **the demo doesn't embarrass us on stage and the platform meets its quality bar**.

**Acceptance Criteria:**

**Given** the full closed loop is working (Story 7.2)
**When** NFR validation runs
**Then** each NFR has a measurable pass/fail:
- **NFR-1 Performance — Orchestrator:** median + p95 first-response time measured over 20 Runs; pass if p95 < 5s
- **NFR-2 Performance — Mini-App:** page load times measured; pass if p95 < 2s
- **NFR-3 Performance — Trace Dashboard:** render times for Runs with 1k entries; pass if < 1s
- **NFR-4 Concurrency:** 5 simultaneous Runs; pass if no degradation (all complete within 2x median)
- **NFR-5 Observability:** every LLM call verified to log provider/model/token counts/latency to audit
- **NFR-6 Security:** RLS verified via direct SQL inspection across 100 random queries — zero cross-tenant leaks
- **NFR-7 Reliability — Resume:** kill arq worker mid-Run; restart; verify Run resumes
- **NFR-8 Reliability — Delivery:** kill subscriber mid-event; restart; verify App Event redelivered
- **NFR-9 PII:** grep audit_trail for known PII patterns; pass if zero hits
- **NFR-10 Cost:** per-Run token spend counter visible in Trace Dashboard; warning fires at 50k tokens
**And** a validation report is generated documenting each NFR's measurement and pass/fail
**And** failing NFRs block demo readiness and surface as issues to fix
**And** the validation suite is re-runnable (CI job or on-demand script)
**And** NFR-6 (security) test cases include edge cases: direct DB query as app role, ORM query bypass, raw SQL injection attempts

### Story 7.5: Demo Run-Through & Polish

As a **demo presenter**,
I want **a rehearsed demo flow and polished UI**,
So that **the judge sees the platform at its best during the hackathon pitch**.

**Acceptance Criteria:**

**Given** NFRs pass (Story 7.4) and bootstrap works (Story 7.3)
**When** the demo run-through is rehearsed
**Then** a demo script document exists in `docs/demo-script.md` covering: opening narrative, UJ-1 walkthrough (Linh configures), UJ-2 walkthrough (judge watches), closing narrative, common Q&A
**And** the demo runs from cold bootstrap to closed loop in under 5 minutes (hackathon time budget)
**And** UI polish items addressed: every transition animation is smooth (UX-DR9), no console errors during demo flow, no layout shift on data load
**And** loading skeletons (UX-DR23) appear for any data fetch > 200ms
**And** error toasts (UX-DR9: 280ms slide-in) configured for common failures (network drop, auth expiry)
**And** the Command Palette (Story 1.11) is enhanced with demo-friendly commands: "Run Loan Pre-Screening", "Open Latest Trace", "Trigger Escalation Demo"
**And** a "demo mode" toggle (env flag) simplifies the UI for presentation (hides dev-only surfaces, larger fonts, slower animations)
**And** the demo script is rehearsed at least twice with zero blocking issues before sign-off
**And** rollback plan documented: if demo fails, reset bootstrap and resume from a known checkpoint
