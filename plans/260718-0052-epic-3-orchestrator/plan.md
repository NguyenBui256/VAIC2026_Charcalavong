---
title: "Epic 3 — Workflow Orchestrator & Human-in-the-Loop"
description: "Orchestrator decomposes Workflow requests into Tasks, dispatches to Specialist Agents, aggregates, escalates to humans; full-stack Run UX"
status: pending
priority: P1
effort: 8 phases (~2 backend foundation + 4 backend + 2 frontend)
branch: rebuild
tags: [epic-3, orchestrator, workflow, state-machine, human-in-the-loop]
created: 2026-07-18
---

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax.
>
> **Bash policy (user rule):** NEVER run bash in the main session. Delegate every shell command (alembic, pytest, ruff, npm) to a subagent. Do NOT commit/push without explicit user consent.

**Goal:** Implement all 8 stories of Epic 3 so a user can define a Workflow in natural language, kick off a Run, watch the Orchestrator decompose it into Tasks dispatched to Specialist Agents (Epic 2), and resolve escalations through a live Run view.

**Architecture:** Hexagonal modular monolith on the DONE Epic-1 foundation + (nearly done) Epic-2 Agent Builder. NEW `orchestrator` backend module (models/service/routes already stubbed empty) owns `workflows`, `workflow_runs`, `tasks` tables behind ports. Orchestrator runs as an LLM-driven coordinator via `LlmPort`; dispatches Tasks to Specialist Agents via `AgentProviderPort` (published Story 2.5, likely needs extension — see Global Constraints); Task state lives in Postgres `tasks` table (AD-3, NOT MCP — MCP is external-tool transport only). Frontend adds `/workflows` list/detail, `/workflows/$id/runs` list, `/workflows/$id/runs/$runId` live view.

**Tech Stack:** Python 3.13, FastAPI 0.139.x, SQLAlchemy 2.x (sync), Pydantic 2.x, Alembic, Postgres 18 (RLS), arq/Redis; React 19, Vite 8, TS 7.x, Tailwind 4, TanStack Query, Vitest, Playwright. Same pin set as Epic 2 — no new deps expected.

**Authoritative task source:** This plan owns full specs for Story 3.1 and 3.2 (foundation, unblock everything else) as `story-3-1-workflow-crud.md` / `story-3-2-run-lifecycle-state-machine.md`. Stories 3.3–3.8 are briefs below (phase P3–P8) — expand each into a `ready-for-dev` artifact (mirroring `_bmad-output/implementation-artifacts/2-N-*.md` shape) before execution, following the same template as the two attached specs.

**Design spec reference:** none yet for Epic 3 — create one at `docs/superpowers/specs/` if `/preview` visuals are needed during dev.

## Global Constraints

- **Baseline:** Epic 1 DONE, Epic 2 nearly complete on `rebuild`. Migration head observed at planning time: `f3a1c9e7b2d4` (`add_tools_integration_id_column`) — **THIS WILL CHANGE.** Epic 2 (Stories 2.6–2.8) is still landing migrations concurrently. **Before creating Epic 3's first migration, the implementer MUST run `cd backend && uv run alembic heads` and set `down_revision` to whatever is THEN current.** Do not hardcode `f3a1c9e7b2d4` from this plan — it is a snapshot, not a target.
- **Do NOT edit** `backend/app/modules/agent_builder/*`, `backend/app/main.py`'s Epic-2 router registrations, or any Epic-2 alembic migration — those are owned by the concurrent Epic-2 agent. Epic 3 work touches `backend/app/modules/orchestrator/*` (currently 3 empty stub files: `models.py`, `routes.py`, `service.py`), adds new alembic migrations, and adds one new router-include line to `main.py` (additive only, at the end of the router-includes block — coordinate/rebase if Epic 2 also touched that block).
- **Reuse (never re-implement):** auth/JWT + `tenant_context` (`app/core/auth.py`); `app/core/deps.py` (`get_tenant_session`, `assume_app_role`, `crud_audit_ids`, `get_mcp_client`); Postgres RLS pattern (mirror `alembic/versions/34cd8281e2b3_create_audit_trail_table.py` DDL, latest example `82478b8e9fea_create_tools_rls.py`); envelope `{data,error,meta}` + `DomainError` handlers (`app/core/errors.py`); `AuditPort`/`PostgresAuditSink` — ONLY writer to `audit_trail` (AD-4); `LlmPort` (`app/core/ports/llm.py`) + Anthropic adapter; `McpClientPort` stub + `get_mcp_client()` factory (AD-3/AD-11, already dept-scope-enforcing); `AgentProviderPort` (`app/core/ports/agent_provider.py`, published Story 2.5).
- **AD-6 — compare-and-set on EVERY state transition (load-bearing, binds 3.2/3.3/3.4/3.6):** single `UPDATE ... WHERE id=? AND status=?`; caller MUST check `rowcount == 1`; `rowcount == 0` → abandon cleanly, never proceed. Applies to `workflow_runs.status` (`pending|running|awaiting_human|completed|failed|timed_out`) AND `tasks.status` (`pending|claimed|completed|failed`). No SELECT-then-UPDATE without the guard (Divergence 4, Divergence 8).
- **AD-10 — tenant context across the arq boundary (load-bearing, binds every background job in 3.2/3.4):** `contextvars.ContextVar` does NOT survive the arq worker process boundary. Enqueuer MUST materialize `tenant_id` into arq job kwargs at enqueue time. Worker function's FIRST statement MUST call `tenant_context.set(tenant_id)` + `SET LOCAL app.tenant_id` on its DB session, sourced from the job payload — never assume inherited context. A Run cannot transition to `running` unless tenant context is set first.
- **AD-11 / MCP dept scope (binds 3.4 Tool/KB calls inside Task execution):** every `McpClientPort` call carries `tenant_id`+`department_id` matching the calling Agent; client-side raise on mismatch — already enforced by `get_mcp_client(agent_department_id=...)` factory, reuse it, do not bypass.
- **AD-4 — audit (binds ALL stories):** `audit.log()` is the only path to `audit_trail`; failure crashes the calling Run (never swallow). Story 3.1 (CRUD, not a Run) reuses the `crud_audit_ids` stopgap from `app/core/deps.py`. Stories 3.2+ (real Run steps) MUST use the real `run_id`/`step_id` — this is the graduation point Epic 2 punted on (OQ-1 handoff, see Open Questions).
- **IDs:** UUID v7 via `app.core.ids.uuid7` (never autoincrement). Timestamps UTC ISO-8601 ms, `timestamptz`.
- **TDD:** RED → GREEN for every task. DoD (AR-14): test evidence (`file:line` PASSED + green run) AND production code reference (`file:line`).
- **Function size ceiling:** 50 lines (backend + frontend). Naming: Python `snake_case`; routes `kebab-case`; React `PascalCase`; CSS `kebab-case`.
- **Domain code reads `tenant_context.get()`** — NEVER accepts `tenant_id` as an argument (except the one sanctioned arq-worker-bootstrap exception under AD-10).
- **Async jobs: arq only.** Never swallow exceptions; never return `None` to mean error.
- **Rule of Three** before extracting a shared helper/port.

---

## Phase 1: Story 3.1 — Workflow Definition CRUD & UI *(HARD GATE — foundation)*

**Full spec:** `story-3-1-workflow-crud.md`

**Depends on:** Epic 1 (auth, RLS, envelope, audit) + Epic 2 pattern reuse only — no Epic-2 code dependency, can start once Epic 2's alembic head is known.

**Deliverable summary:** `workflows` table + RLS migration (down_revision = current alembic head at execution time); `orchestrator` module's `models.py`/`service.py`/`routes.py` filled for Workflow CRUD only (Run lifecycle is 3.2); `/workflows` list + `/workflows/$id` Definition tab UI; audit on every CRUD op.

**Key ACs to verify green:** POST 201 shape (id UUID v7, tenant_id, owner_id, created_at, version); GET/list tenant-scoped (RLS); cross-tenant GET → 404; list page (search + owner filter); Definition tab (Name/Description/Constraints chip-list, UX-DR8 validation, unsaved-changes guard); audit `workflow.created|updated`.

**Migration ordering note:** THIS IS EPIC 3's FIRST MIGRATION. Run `uv run alembic heads` immediately before writing the revision — do not assume any head value from this plan.

**TDD/DoD:** Same discipline as Epic-2 Story 2.1 (RED test importing missing model/route → migration → service → routes → GREEN → DoD evidence).

- [ ] Execute `story-3-1-workflow-crud.md` tasks T1→Tn in order.
- [ ] Verify all ACs green with evidence.

**Gate:** P2 (Run lifecycle) depends on the `workflows` table existing. P3–P8 all depend on P1+P2.

---

## Phase 2: Story 3.2 — Workflow Run Lifecycle & State Machine *(HARD GATE — foundation)*

**Full spec:** `story-3-2-run-lifecycle-state-machine.md`

**Depends on:** P1 (`workflows` table + FK target).

**Deliverable summary:** `workflow_runs` + `tasks` tables + RLS migration (down_revision = P1's migration); compare-and-set state machine for both (AD-6); `POST /workflows/{id}/runs` enqueues arq job with materialized `tenant_id` (AD-10); arq worker `run_workflow(run_id, tenant_id)` bootstraps tenant context first, then CAS `pending→running`; startup poller resumes crashed `running` Runs; every transition emits `audit.log(type="workflow_run.transition")`.

**Key ACs to verify green:** POST /runs → 201 `pending`; arq job enqueued with materialized tenant_id; worker CAS `pending→running`, `rowcount==0` → abandon; concurrent-worker test proves no double-transition; audit entry per transition with `{from,to}`.

**Migration ordering note:** down_revision chains off P1's Workflow migration (same execution-time-checked pattern — re-verify head right before writing, in case other work landed between P1 and P2 execution).

**TDD/DoD:** Concurrent-transition test is load-bearing (Divergence 4/8) — two threads/sessions racing `UPDATE...WHERE status='pending'` must show only one `rowcount==1`.

- [ ] Execute `story-3-2-run-lifecycle-state-machine.md` tasks T1→Tn in order.
- [ ] Verify all ACs green with evidence, including the concurrency test.

**Gate:** Everything downstream (P3–P8) waits on P1+P2 green. Do not start P3 until the state machine + tenant-bootstrap pattern is proven.

---

## Phase 3: Story 3.3 — Orchestrator Decomposition *(Backend)*

**Brief — expand to full artifact before execution.**

**Depends on:** P2 (Run in `running` state); `LlmPort` (Story 1.6, DONE); `AgentProviderPort` (Story 2.5, published — read-only consumption, see Open Question about extension).

**Deliverable:** Orchestrator reads Workflow description via `LlmPort.complete(...)`, produces Tasks conforming to Task Schema (PRD §A1: `task/target_agent_id/input/output/expected/criteria`); validate each Task against the schema-meta-schema — invalid → drop + `audit.log(type="task.dropped_invalid")`; unknown/wrong-Department `target_agent_id` → reject + `audit.log(type="task.routing_rejected")`; INSERT valid Tasks into `tasks` table (`status='pending'`); log `audit.log(type="orchestrator.decomposed", input={request, workflow_description}, output={tasks, routing_rationale})`.

**Key ACs:** FR-8 consequences — schema validation, unknown-agent rejection, decomposition rationale visible in Audit Trail, reproducibility (same request+Workflow+Agent-set → similar Task graph).

**Files (anticipated):** `backend/app/modules/orchestrator/models.py` (Task model — may already partially exist from P2), `backend/app/modules/orchestrator/service.py` (`decompose(run_id) -> list[Task]`), new `backend/app/core/schemas/task_schema.py` or inline Pydantic model for Task Schema validation, tests under `backend/tests/integration/test_orchestrator_decomposition.py`.

**Note:** Routing "considers the Agent's Department and declared capabilities" — requires reading `agents` table (read-only cross-module query via `agent_builder`'s public service interface, AD-1 — do NOT reach into its models directly).

- [ ] Expand into `story-3-3-orchestrator-decomposition.md` (or execute inline) once P1+P2 are green.

---

## Phase 4: Story 3.4 — Task Dispatch, Claim & Aggregation *(Backend)*

**Brief — expand to full artifact before execution.**

**Depends on:** P3 (Tasks exist in `tasks` table); `AgentProviderPort` extension for dispatch (see Open Question); `McpClientPort` (Tool/KB calls during Task execution, dept-scoped per AD-11).

**Deliverable:** Specialist Agent worker polls `tasks` for `status='pending' AND target_agent_id=?`; CAS claim `pending→claimed` (AD-6, `rowcount==1` check — Divergence 4); executes Task (via Agent's `LlmPort` config + `AgentProviderPort.retrieve` for KB + `McpClientPort` for Tools); writes `tasks.result`, CAS `claimed→completed|failed`; 60s timeout → `failed` w/ reason `timeout`, retry ×2 exponential backoff (2s, 8s) per FR-9; Orchestrator aggregates all responses/timeouts into one Run result, logs `audit.log(type="orchestrator.aggregated")`; Run CAS `running→completed|failed`.

**Key ACs:** FR-9 consequences — retry policy, 60s timeout, aggregation audit visibility; concurrency test — no Task double-claimed by concurrent Specialist Agent workers (Divergence 4, load-bearing).

**Files (anticipated):** `backend/app/modules/orchestrator/service.py` (`claim_task`, `dispatch_and_execute`, `aggregate`), arq worker registration (new job function, mirror P2's `run_workflow` tenant-bootstrap pattern — AD-10 applies again here since Task execution is itself background work), tests for concurrent-claim race.

- [ ] Expand into `story-3-4-task-dispatch-claim-aggregation.md` once P3 is green.

---

## Phase 5: Story 3.5 — Per-Step Feedback Incorporation *(Backend)*

**Brief — expand to full artifact before execution.**

**Depends on:** P4 (Task results exist).

**Deliverable:** `tasks.result` includes structured feedback `{confidence: float 0-1, flags: enum[requires_human_validation|policy_conflict|missing_information|cross_department_dependency], rationale: text}` (FR-11); Orchestrator aggregation (P4) consumes feedback to decide aggregate/escalate/follow-up per confidence threshold (default 0.7, configurable per Workflow — needs a `workflow.confidence_threshold` column, likely added in P1's migration or a small P5 migration); decision logged `audit.log(type="orchestrator.feedback_consumed")`.

**Key ACs:** feedback is structured never free-form; threshold configurable per Workflow, not hard-coded.

**Note:** This tightly couples with P4's aggregation logic — consider merging P4+P5 execution if the feedback shape is designed together (feedback object should exist on Day 1 of P4, not bolted on after — avoid rework). Flag this sequencing choice to the implementer.

- [ ] Expand into `story-3-5-per-step-feedback.md` once P4 is green (or merge into P4 artifact).

---

## Phase 6: Story 3.6 — Human-in-the-Loop Escalation *(Backend)*

**Brief — expand to full artifact before execution.**

**Depends on:** P5 (feedback-driven escalation decision).

**Deliverable:** On escalate decision, emit `{run_id, conflicting_steps, suggested_resolutions, rationale}`, CAS `running→awaiting_human` (AD-6); appears in global Escalation Inbox (topbar bell — cross-cutting frontend, may need a shared count endpoint); `POST /runs/{id}/resolve` records `{user_id, timestamp, rationale, decision: resolved|overridden|rejected}`, CAS back to `running` or `completed`; 5-min timeout (configurable per Workflow) CAS `awaiting_human→timed_out` via arq scheduled check; full lifecycle audited (`escalation.created|resolved|timed_out`).

**Key ACs:** FR-10 consequences; test — Run cannot leave `awaiting_human` without resolution or timeout (CAS guard, no bypass path).

**Files (anticipated):** new `POST /runs/{id}/resolve` route, arq periodic job for timeout sweep (mirror `cron_jobs` pattern per AD-10), `backend/app/modules/orchestrator/models.py` (`escalations` table or fields on `workflow_runs`).

- [ ] Expand into `story-3-6-human-in-the-loop-escalation.md` once P5 is green.

---

## Phase 7: Story 3.7 — Workflow Runs List UI *(Frontend)*

**Brief — expand to full artifact before execution.**

**Depends on:** P2 (Run endpoints exist — list can ship before P3–P6 are fully done since it only needs `GET /workflows/{id}/runs`).

**Deliverable:** `/workflows/$id/runs` list — Run ID, status pill (UX-DR11), started-at, duration, triggered-by, escalation indicator; filter by status (multi-select) + time range; sort by started-at/duration; cursor pagination >50 (AR-14 `meta`); 1s-interval live status pill for `running`/`awaiting_human` rows; empty state (UX-DR23); row click → Run View; topbar "Run" split-button.

**Key ACs:** all per Story 3.7 ACs verbatim above.

**Note:** Can start once P2 is green — does not need P3–P6's decomposition/escalation logic to build the list shell, only needs real status values to exist in the enum.

- [ ] Expand into `story-3-7-workflow-runs-list-ui.md` once P2 is green.

---

## Phase 8: Story 3.8 — Live Run View with Escalation Panel *(Frontend, closes Epic 3)*

**Brief — expand to full artifact before execution.**

**Depends on:** P2 (Run/Task endpoints) + P6 (Escalation Panel needs `/runs/{id}/resolve` + escalation data shape) for full functionality; can scaffold Header+Task Stream against P2+P3+P4 earlier, but Escalation Panel is blocked on P6.

**Deliverable:** `/workflows/$id/runs/$runId` — Header (Run ID, status pill, duration counter, trigger source), Task Stream (1s poll, trace-step animation UX-DR9, expand-for-detail), Escalation Panel (visible only `awaiting_human`, per Story 3.6 shape, Resolve/Override/Reject → `POST /runs/{id}/resolve`, no full reload); final result panel with "View in Trace Dashboard" link (Epic 6, stub link ok); `aria-live` regions (UX-DR12); shareable deep-link URL; "reconnecting" indicator on poll failure.

**Key ACs:** all per Story 3.8 ACs verbatim above.

- [ ] Expand into `story-3-8-live-run-view.md` once P2+P6 are green. This closes Epic 3.

---

## Definition of Done (Epic 3)

- [ ] P1–P8 all green; every phase has DoD evidence (`file:line` test + production ref).
- [ ] `workflows` / `workflow_runs` / `tasks` all persist Tenant-scoped, RLS-verified.
- [ ] Compare-and-set proven under concurrency for BOTH `workflow_runs.status` and `tasks.status` (Divergence 4 + Divergence 8 closed).
- [ ] Tenant context proven to survive the arq boundary for both `run_workflow` and Task-execution worker entrypoints (Divergence 1 closed).
- [ ] Every Orchestrator step (decomposition, dispatch, aggregation, escalation) audited via `AuditPort` with the real `run_id`/`step_id` (graduates past Epic 2's `crud_audit_ids` stopgap for Run-scoped work).
- [ ] `WorkflowRunPort` (start/status/escalate) published for Epic 5 (Automation & Triggers) per epics.md L319.
- [ ] Full backend + frontend suites green; ruff/lint clean.

## Open Questions

1. **AgentProviderPort dispatch gap (blocks P3/P4 design):** `AgentProviderPort` (Story 2.5) currently exposes only `retrieve(agent_id, query, ...) -> list[RetrievalPassage]` (KB retrieval). Story 3.4 needs the Orchestrator to dispatch a full Task to a Specialist Agent — i.e. run the Agent's system prompt + model config (`LlmPort`) + optionally invoke its Tools (`McpClientPort`) + KB (`retrieve`), and return a structured Task result. This is a materially bigger capability than `retrieve`. **Recommend:** extend `AgentProviderPort` with `execute_task(agent_id, task_payload, *, tenant_id, department_id) -> TaskResult` in Phase 3/4, OR have `orchestrator.service` read Agent config directly via `agent_builder`'s public service interface (not its models, AD-1) and orchestrate `LlmPort`/`McpClientPort` calls itself. Needs a decision before P3/P4 detailed design — flagged, not resolved here.
2. **Confidence-threshold storage:** FR-11 requires per-Workflow configurable confidence threshold (default 0.7). Not in Story 3.1's AC list (no `constraints`-adjacent field mentioned for it). Recommend adding `confidence_threshold FLOAT NOT NULL DEFAULT 0.7` to the `workflows` table in P1's migration (cheap now) rather than a follow-up P5 migration — flagged in P1 spec as a design call for the implementer.
3. **Escalation timeout mechanism (P6):** 5-min `awaiting_human→timed_out` sweep needs a periodic arq job (`cron_jobs`-style, per AD-10 "Schedule Triggers fire without HTTP context" pattern) scanning all tenants under `BYPASSRLS`. This is architecturally identical to Epic 5's Schedule Trigger fan-out (not yet built) — Epic 3 will effectively pre-build a slice of that mechanism. Confirm whether to inline a minimal version in P6 or coordinate with Epic 5 scope to avoid duplicate work.
4. **Migration ordering coordination:** Epic 2 (Stories 2.6–2.8) is still landing migrations on `rebuild`. P1's `down_revision` MUST be re-checked via `uv run alembic heads` at actual execution time, not assumed from this plan's `f3a1c9e7b2d4` snapshot.
