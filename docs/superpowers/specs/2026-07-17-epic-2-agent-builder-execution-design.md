# Epic 2 — Specialist Agent Builder: Execution Design

**Date:** 2026-07-17
**Branch:** rebuild
**Baseline commit:** `4e2c5ad` (Epic 1 DONE — stable contract base)
**Scope:** Execution/sequencing design for all 8 Epic-2 stories (specs already `ready-for-dev` in `_bmad-output/implementation-artifacts/2-*.md`). This is NOT a re-design of the stories — it sequences them into an executable plan and pins the two cross-cutting open questions.

---

## 1. Foundation & constraints (reuse, do not re-implement)

Epic 1 is the stable contract base. Reuse verbatim:

- Auth/JWT + `tenant_context` contextvar (`core/auth.py`, `core/tenant_context.py`)
- Postgres RLS pattern (mirror migration `34cd8281e2b3_create_audit_trail_table.py`)
- API envelope `{data, error, meta}` + `DomainError` handlers (`core/errors.py`)
- `AuditPort` / `PostgresAuditSink` — the ONLY writer to `audit_trail` (AD-4)
- `LlmPort` + Anthropic adapter (`core/ports/llm.py`, `core/adapters/anthropic.py`)
- `McpClientPort` **stub** — VAIC is an MCP *client* only; the MCP server + real `rag.search` tool are OUT OF SCOPE (AD-3)

Principles: TDD (RED→GREEN); DoD per AR-14 (test evidence `file:line` + green run AND production `file:line`); functions ≤ 50 lines; naming `snake_case` (py) / `PascalCase` (react) / `kebab-case` (routes, css); IDs UUID v7; timestamps UTC ISO-8601 ms `timestamptz`.

## 2. Cross-cutting open questions → resolved in Phase 0

- **OQ-2 (shared session dep):** `get_tenant_session` currently in `tenant/routes.py:101`. Rule-of-Three met (tenant + agent_builder + 2.2/2.6). **Resolution:** promote to `app/core/deps.py` and import from there (AD-1 forbids reaching into another module's internals).
- **OQ-1 (audit convention for non-Run CRUD):** CRUD audit entries have no Workflow Run. **Resolution (stopgap):** `run_id = str(agent.id)`, `step_id = str(uuid7())`, `latency_ms = 0`, `model = ""`. MUST route through `AuditPort` — never bypass (AD-4).

## 3. Phasing & dependencies

One phase per story + Phase 0. Execute sequentially in the main session; delegate bash/tests to a subagent (per user rule).

| Phase | Story | Type | Depends on | Core work |
|---|---|---|---|---|
| **P0** | — | Cross-cut | Epic 1 | `core/deps.py` (promote `get_tenant_session`); pin OQ-1 audit convention |
| **P1** | 2.1 | Backend | P0 | `agents` table + RLS migration (down_rev `34cd8281e2b3`); model/service/routes CRUD; owner/builder scoping; soft-delete (REVOKE DELETE on role); audit wiring |
| **P2** | 2.2 | Frontend | P1 | `/agents` list (search, Dept filter) + Detail shell 6 tabs + Identity tab |
| **P3** | 2.3 | Frontend | P2 + LlmPort | Model tab (provider/model picker from Model Layer) + Prompt tab |
| **P4** | 2.4 | Full-stack | P1 | KB upload/storage (doc intake, chunk/index) + KB tab UI |
| **P5** | 2.5 | Backend | P4 | `AgentProviderPort` + `kb_search` runtime via `McpClientPort` (AD-11 dept scope) |
| **P6** | 2.6 | Full-stack | P1 | Tool config (input/output JSON Schema, embedded Python sandbox) + Tools tab |
| **P7** | 2.7 | Full-stack | P1 | API Integration config (stubbed connectors, encrypted creds) + tab |
| **P8** | 2.8 | Integration | P2–P7 | Wire all tabs into Agent Builder surface + e2e |

**Critical path:** `P0 → P1 → { P2→P3 (FE) ‖ P4→P5 (KB) ‖ P6 ‖ P7 } → P8`.
P1 is the hard gate — everything waits on it. Post-P1 branches are theoretically parallel, but executed sequentially per the table to avoid file conflicts in a single session.

## 4. Contracts published (consumed by later epics)

- `AgentProviderPort` (P5) → Epic 3 Orchestrator dispatches task/retrieval.
- `agents` table + CRUD → foundation for Workflow routing.

## 5. Testing & risks

Per phase: integration test for cross-tenant RLS (empty result), API response shape, authz 403 paths, exactly-one audit entry with correct `type`.

- **P6 embedded-Python sandbox** — OQ-6 (PRD) undecided. MVP proposal: subprocess + restricted builtins, no network, 10s CPU, 128MB. Flag if a stronger sandbox is required.
- **P4/P5 KB retrieval** depends on MCP server's `rag.search` (not owned by VAIC). Dev/test runs only through the `McpClientPort` stub.

## 6. Out of scope

- MCP server implementation (AD-3).
- Anything in PRD §5 / §6.2 non-goals.
- Epic 3+ work (Orchestrator, Mini-App, Actions, Trace, Integration).

## Open questions carried forward

1. P6 sandbox tech (OQ-6) — confirm subprocess-based MVP is acceptable.
2. Parallelization: confirmed sequential per user; revisit if a team/worktree flow is desired later.
