# Epic 2 — Specialist Agent Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Bash policy (user rule):** NEVER run bash in the main session. Delegate every shell command (alembic, pytest, ruff, npm) to a subagent. Do NOT commit/push without explicit user consent.

**Goal:** Implement all 8 stories of Epic 2 so a user can configure a Specialist Agent end-to-end (identity, Dept-scoped KB, Tools, API Integrations, Model) persisted as a Tenant-scoped record ready for Workflow execution.

**Architecture:** Hexagonal modular monolith on top of the DONE Epic-1 foundation. The `agent_builder` backend module (models/service/routes) sits behind ports; frontend adds the Agent Builder surface (list + 6-tab detail). Reuse Epic 1's auth, RLS, envelope, audit sink, LlmPort, and McpClientPort stub — do not re-implement them.

**Tech Stack:** Python 3.13, FastAPI 0.139.x, SQLAlchemy 2.x (sync), Pydantic 2.x, Alembic, Postgres 18 (RLS), arq/Redis, `anthropic` SDK, `mcp` SDK (client); React 19, Vite 8, TS 7.x, Tailwind 4, TanStack Query, Vitest, Playwright.

**Authoritative task source:** Each phase P1–P8 maps to one `ready-for-dev` BMad artifact under `_bmad-output/implementation-artifacts/2-N-*.md`. Those files hold the bite-sized TDD tasks (T1..Tn), exact file paths, and code. This plan orchestrates them and owns Phase 0 (cross-cutting prep, no artifact). **Do not duplicate story code here — open the artifact, execute its tasks in order.**

**Design spec:** `docs/superpowers/specs/2026-07-17-epic-2-agent-builder-execution-design.md`

## Global Constraints

- Baseline commit: `4e2c5ad` (Epic 1 DONE). Migration head before P1: `34cd8281e2b3`.
- Reuse (never re-implement): auth/JWT + `tenant_context`; Postgres RLS (mirror `34cd8281e2b3_create_audit_trail_table.py`); envelope `{data,error,meta}` + `DomainError` handlers; `AuditPort`/`PostgresAuditSink` = ONLY writer to `audit_trail` (AD-4); `LlmPort`+Anthropic adapter; `McpClientPort` **stub** (VAIC is MCP client only — server OUT OF SCOPE, AD-3).
- TDD: RED → GREEN for every task. DoD (AR-14): test evidence (`file:line` PASSED + green run) AND production code reference (`file:line`).
- IDs UUID v7 (never autoincrement). Timestamps UTC ISO-8601 ms, `timestamptz`.
- Function size ceiling: 50 lines (backend + frontend).
- Naming: Python `snake_case`; routes `kebab-case`; React components `PascalCase`; CSS `kebab-case`.
- Domain code reads `tenant_context.get()` — NEVER accepts `tenant_id` as an argument. RLS owns tenant filtering (no Python `WHERE tenant_id`).
- Async jobs: arq only. Never swallow exceptions; never return `None` to mean error.
- Rule of Three before extracting a shared helper/port.

---

## Phase 0: Cross-cutting prep (NEW — no BMad artifact)

**Files:**
- Create: `backend/app/core/deps.py`
- Modify: `backend/app/modules/tenant/routes.py:101` (move `get_tenant_session` out), update its importers
- Reference: `backend/app/core/ports/audit.py`, `backend/app/core/ids.py` (uuid7)

**Interfaces:**
- Produces: `app.core.deps.get_tenant_session` (FastAPI dependency yielding a tenant-scoped SQLAlchemy `Session` with `SET LOCAL app.tenant_id` already applied) — consumed by P1, P4, P6, P7 routes.
- Produces: audit convention for non-Run CRUD (OQ-1): `run_id=str(entity.id)`, `step_id=str(uuid7())`, `latency_ms=0`, `model=""`.

- [ ] **Step 1: Locate current `get_tenant_session`.** Read `backend/app/modules/tenant/routes.py` around line 101; note its exact body, imports, and every module importing it (grep `get_tenant_session`).

- [ ] **Step 2: Write failing test for the shared dep.** Add `backend/tests/integration/test_core_deps.py` asserting `from app.core.deps import get_tenant_session` imports and that a request using it sets `app.tenant_id` (reuse the two-tenant fixture from `tests/integration/conftest.py`; assert a cross-tenant read returns empty).

- [ ] **Step 3: Run test — expect FAIL** (`ImportError: cannot import name 'get_tenant_session'`). Delegate to subagent: `cd backend && uv run pytest tests/integration/test_core_deps.py -v`.

- [ ] **Step 4: Create `core/deps.py`.** Move the `get_tenant_session` body verbatim from `tenant/routes.py` into `app/core/deps.py`. Keep signature and yield semantics identical. Do NOT reach into any module's internals (AD-1).

- [ ] **Step 5: Re-point importers.** In `tenant/routes.py` and any other importer, replace the local definition/import with `from app.core.deps import get_tenant_session`. Remove the old definition.

- [ ] **Step 6: Pin OQ-1 audit convention.** Add a short module docstring/comment in `core/deps.py` (or a helper `crud_audit_ids(entity_id) -> tuple[run_id, step_id]`) documenting the stopgap so P1/P4/P6/P7 reuse it identically. Keep ≤ 50 lines.

- [ ] **Step 7: Run full suite — expect GREEN.** Subagent: `cd backend && uv run pytest && uv run ruff check app tests`. Confirm no regression in existing tenant tests.

- [ ] **Step 8: Record DoD evidence.** Note passing `test_core_deps.py::...` (`file:line`) + production ref `app/core/deps.py:<lines>`. (Commit only if user consents.)

**Deliverable:** Shared tenant-session dependency + pinned CRUD-audit convention. Unblocks P1.

---

## Phase 1: Story 2.1 — Agent CRUD, Identity & Department Scoping  *(HARD GATE)*

**Artifact (authoritative tasks T1–T7):** `_bmad-output/implementation-artifacts/2-1-agent-crud-identity-department-scoping.md`

**Depends on:** P0 (uses `core/deps.get_tenant_session`, `crud_audit_ids`).

**Deliverable summary:** `agents` table + RLS migration (down_rev `34cd8281e2b3`; GRANT SELECT/INSERT/UPDATE, REVOKE DELETE → soft-delete at DB); `agent_builder` model/service/routes; CRUD with owner/builder scoping; soft-delete; one audit entry per op (`agent.created|updated|deleted`).

**Key ACs to verify green:** AC1 POST 201 shape; AC3 cross-tenant GET → 404 (not 403); AC4/AC5 tenant-scoped list + Dept filter; AC6 non-owner/non-builder PATCH → 403; AC7 soft-delete only (row still in DB); AC8 audit entry per op; AC9 raw-SQL cross-tenant empty; AC10 non-builder mutate → 403.

**Execution notes:**
- Use `core/deps.get_tenant_session` (from P0), not `tenant/routes` import.
- Audit ids via P0 convention; route through `AuditPort` only (never direct SQL to `audit_trail`).
- Register router in `app/main.py` mirroring `main.py:31`.
- Delegate all `alembic`/`pytest`/`ruff` to subagent. Migration must be idempotent (run `upgrade head` twice).

- [ ] Execute artifact tasks T1→T7 in order (model → migration+RLS → service → audit wiring → routes → tests → green+DoD).
- [ ] Verify all 10 ACs green with evidence.

**Gate:** Everything downstream waits on P1. Do not start P2–P7 until P1 is green.

---

## Phase 2: Story 2.2 — Agent List & Detail Shell + Identity Tab  *(Frontend)*

**Artifact:** `_bmad-output/implementation-artifacts/2-2-agent-list-detail-shell-identity-tab.md`
**Depends on:** P1 (consumes `/agents` list/get/patch endpoints).
**Deliverable:** `/agents` searchable list (Dept filter, 200ms debounce, empty state UX-DR23) + `/agents/$id` detail with 6-tab nav (Identity default) + Identity form (Name/Dept/System Prompt/Status, required `*`, validate-on-blur, dirty-dot, unsaved-changes guard).
**Execution:** Follow artifact tasks; reuse Epic-1 primitives (Button/Card/Form/StatusPill/Table). Vitest per component. Delegate `npm`/`vitest` to subagent.

- [ ] Execute artifact tasks in order; verify list, detail shell, Identity tab ACs green.

---

## Phase 3: Story 2.3 — Per-Agent Model Selection & Prompt Editing  *(Frontend)*

**Artifact:** `_bmad-output/implementation-artifacts/2-3-per-agent-model-selection-prompt-editing.md`
**Depends on:** P2 (tabs shell) + `LlmPort`/Model Layer for provider list.
**Deliverable:** Model tab (Provider dropdown = runtime-configured providers, Anthropic active + others "Not configured"; Model dropdown; Parameters temp/max_tokens) persisting `{provider, model_name, parameters}` as data (AD-7); Prompt tab (mono editor, char count, context-window warn).
**Execution:** Follow artifact tasks; changing model = config-only, no code change (FR-5).

- [ ] Execute artifact tasks; verify Model + Prompt tab ACs green.

---

## Phase 4: Story 2.4 — Knowledge Base Upload & Storage  *(Full-stack)*

**Artifact:** `_bmad-output/implementation-artifacts/2-4-knowledge-base-upload-storage.md`
**Depends on:** P1 (agent scope) — note this file is currently modified in git (`M`); reconcile before executing.
**Deliverable:** KB upload (PDF/TXT/MD/DOCX ≤20MB), doc intake → chunk/index, KB tab UI (upload + document list). Dept-scoped KB isolation.
**Execution:** Use `DocIntakePort`. Retrieval indexing per artifact; embedding provider per Architecture. Delegate tests to subagent.

- [ ] Reconcile the working-tree change in the artifact, then execute its tasks; verify upload/storage + isolation ACs green.

---

## Phase 5: Story 2.5 — Knowledge Base Retrieval at Runtime  *(Backend)*

**Artifact (tasks T1–T5):** `_bmad-output/implementation-artifacts/2-5-knowledge-base-retrieval-runtime.md`
**Depends on:** P4 (indexed docs).
**Deliverable:** NEW `app/core/ports/agent_provider.py` (`AgentProviderPort` Protocol, `@runtime_checkable`, `retrieve(agent_id, query, *, tenant_id, department_id, top_k=5) -> list[RetrievalPassage]`); `RetrievalPassage{passage, document_name, chunk_reference, score}`; `app/modules/agent_builder/kb_retrieval.py` `kb_search` routing via `McpClientPort.call_tool("rag.search", ...)` with the Agent's OWN dept (AD-11); audit `type="kb.retrieval"`.
**Key ACs:** AC2 dept-mismatch RAISES before network (assert `call_tool` never awaited); AC4 cross-dept → empty; AC5 audit once with `passage_count`/`top_score`; AC6 exposed via `AgentProviderPort` for Epic 3.
**Execution:** Backend/runtime only — NO UI. Depend on `McpClientPort` stub; do NOT build the MCP server or real `rag.search` (AD-3).

- [ ] Execute artifact tasks T1→T5 (RED tests → port → runtime fn → green → DoD); verify ACs.

**Contract published:** `AgentProviderPort` → consumed by Epic 3.

---

## Phase 6: Story 2.6 — Per-Agent Tool Configuration  *(Full-stack)*

**Artifact:** `_bmad-output/implementation-artifacts/2-6-per-agent-tool-configuration.md`
**Depends on:** P1.
**Deliverable:** Tool registration (display name, header incl. auth, input/output JSON Schema, optional embedded Python) + Tools tab. Input-schema validation on invoke; output-schema failure logged to audit.
**Risk (OQ-6):** embedded-Python sandbox undecided. MVP: subprocess + restricted builtins, no network, 10s CPU, 128MB (per `core/ports/sandbox.py`). Flag if stronger sandbox needed.
**Execution:** Follow artifact tasks; delegate tests to subagent.

- [ ] Execute artifact tasks; verify Tool config + validation + sandbox ACs green.

---

## Phase 7: Story 2.7 — Per-Agent API Integration Configuration  *(Full-stack)*

**Artifact:** `_bmad-output/implementation-artifacts/2-7-per-agent-api-integration-configuration.md`
**Depends on:** P1.
**Deliverable:** API Integration registration (`{base_url, auth_header, schema}`) referenced by Tools; encrypted credential storage (never inline secrets, NFR-6); `test_integration` pings `GET {base_url}/health` without returning the header (AC9). Integrations point at stubbed FastAPI endpoints (no live OAuth — PRD §5).
**Execution:** Follow artifact tasks T1–Tn; delegate tests to subagent.

- [ ] Execute artifact tasks; verify integration config + `test_integration` ACs green.

---

## Phase 8: Story 2.8 — Agent Builder Surface Integration  *(Integration)*

**Artifact:** `_bmad-output/implementation-artifacts/2-8-agent-builder-surface-integration.md`
**Depends on:** P2–P7 (all tabs).
**Deliverable:** Wire all 6 tabs into the Agent Builder surface as one coherent flow; e2e (Playwright) for the full configure-an-Agent journey (UJ-1 steps 1–5).
**Execution:** Follow artifact tasks; run e2e via subagent. This closes Epic 2.

- [ ] Execute artifact tasks; verify end-to-end Agent configuration flow green.

---

## Definition of Done (Epic 2)

- [ ] P0–P8 all green; every phase has DoD evidence (`file:line` test + production ref).
- [ ] `agents` + KB + Tools + API-Integration + Model config all persist Tenant/Dept-scoped, RLS-verified.
- [ ] `AgentProviderPort` published for Epic 3.
- [ ] No hardcoded secrets; audit entries emitted for every mutation via `AuditPort`.
- [ ] Full backend + frontend suites green; ruff/lint clean.

## Open questions

1. **OQ-6** — P6 embedded-Python sandbox tech: confirm subprocess-based MVP acceptable, or specify (Docker/gVisor/WASM/E2B).
2. **P4 artifact** currently shows as modified in git — confirm intended working-tree state before executing.
3. Commit/push cadence — plan assumes NO auto-commit (user rule); confirm when to commit each phase.
