---
baseline_commit: 4e2c5ad3cb823b8edb5f8ce6d0ea8b3d94a4fd1c
---

# Story 2.6: Per-Agent Tool Configuration

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **user configuring a Specialist Agent**,
I want **to register Tools with structured input/output schemas that the Agent can invoke during a Workflow Run**,
so that **the Agent can take actions beyond text generation, validated against a contract**.

## Acceptance Criteria

Sourced verbatim from [epics.md#Story-2.6 L779-793].

1. **AC1 -- Register a Tool with schemas (+ optional embedded Python)** (epics.md L781-784): Given an Agent exists and the user opens the Tools tab, when the user clicks "New Tool" and provides `{display_name, header (including auth), input_schema (JSON Schema), output_schema (JSON Schema), optional embedded_python}`, then the Tool is registered against the Agent with a UUID v7 `tool_id`, **and** both `input_schema` and `output_schema` validate against **JSON Schema draft 2020-12** (i.e. the submitted schemas are themselves checked as valid draft-2020-12 documents at registration time; registration is rejected with a structured error if either is not a valid schema).
2. **AC2 -- Input validated on every invocation; mismatch -> structured error + audit** (epics.md L785-786, FR-3): When an Agent invokes a registered Tool during a Workflow Run, every invocation validates the input against `input_schema`; a valid call is logged to `audit_trail` via `audit.log()` with `type: "tool.invoked"`, and a mismatched call returns a **structured error** to the Orchestrator and is logged with `type: "tool.rejected"`.
3. **AC3 -- Output validated; failing output rejected + audit** (epics.md L787, FR-3): Output that fails `output_schema` is rejected (not returned to the Orchestrator as success) and logged (a `tool.rejected` audit entry describing the output-schema failure).
4. **AC4 -- Embedded Python runs in the AR-14 subprocess sandbox** (epics.md L788-790): When a Tool has embedded Python, the Python executes in a subprocess sandbox via `SandboxPort.run(...)` with **no network egress, restricted builtins, a 10s CPU cap, and a 128MB memory cap (AR-14)**; input is passed via **stdin** and output read from **stdout**.
5. **AC5 -- Sandbox timeout / memory breach terminates + audits `tool.sandbox_violation`** (epics.md L791): A sandbox timeout or memory breach terminates the subprocess and logs `type: "tool.sandbox_violation"` to `audit_trail`.
6. **AC6 -- Tools tab UI provides a JSON Schema editor with live validation** (epics.md L792): The Tools tab UI provides a JSON Schema editor (e.g. monaco-editor) with live validation of the entered schema (UX-DR7 code/JSON block, UX-DR16 Tools tab).
7. **AC7 -- "Test Tool" affordance** (epics.md L793): A "Test Tool" affordance lets the user invoke the Tool with sample input and see the output (useful during development). It exercises the same registration -> input-validate -> (sandbox|MCP) -> output-validate path, so the user sees real validation/sandbox errors before a Workflow Run ever calls the Tool.

## Tasks / Subtasks

- [ ] **T1 -- `tools` model + migration (RLS)** (AC: #1)
  - [ ] T1.1 `app/modules/agent_builder/models.py` (UPDATE) -- add `Tool(Base)` SQLAlchemy 2.x `Mapped[...]` declarative, `__tablename__ = "tools"`. Columns: `id` (`UUID` PK, `default=uuid7` -> UUID v7 `tool_id`), `agent_id UUID NOT NULL` (FK `agents.id`, `ondelete="CASCADE"`), `tenant_id UUID NOT NULL` (FK `tenants.id`, `ondelete="CASCADE"`), `department_id UUID NOT NULL` (FK `departments.id`, `ondelete="RESTRICT"`).
  - [ ] T1.2 Domain columns: `display_name String(255) NOT NULL`, `header JSONB NOT NULL` (includes auth -- stored, never returned in full to the client per AR-14 stored-credentials), `input_schema JSONB NOT NULL`, `output_schema JSONB NOT NULL`, `embedded_python Text nullable` (NULL => MCP-routed tool, non-NULL => sandbox-routed). Soft-delete + timestamps mirroring the `agents` table (`is_deleted`, `deleted_at`, `created_at`, `updated_at`).
  - [ ] T1.3 Alembic migration `create tools rls` -- `down_revision` = current head (the `agents` migration from Story 2-1; confirm the exact revision id at implementation time -- do NOT hard-code before 2-1 merges). `op.create_table("tools", ...)`; indexes `ix_tools_agent_id`, `ix_tools_tenant_id`.
  - [ ] T1.4 RLS DDL -- copy the exact pattern used for `agents`/`audit_trail`: `ENABLE` + `FORCE ROW LEVEL SECURITY` + `CREATE POLICY tenant_isolation_policy ON tools USING (tenant_id = current_setting('app.tenant_id')::uuid) WITH CHECK (...)`. Grants: `GRANT SELECT, INSERT, UPDATE ON tools TO vaic_app;` + `REVOKE DELETE, TRUNCATE ON tools FROM vaic_app;` (soft-delete-only). `downgrade()` reverses. Idempotent (`upgrade head` twice = no-op).
- [ ] **T2 -- JSON Schema draft 2020-12 validation helper** (AC: #1, #2, #3)
  - [ ] T2.1 `app/modules/agent_builder/schema_validation.py` (NEW) -- thin wrapper over `jsonschema` (Draft 2020-12: `jsonschema.Draft202012Validator`). `validate_schema_document(schema: dict) -> None` uses `Draft202012Validator.check_schema(schema)` to assert the submitted `input_schema`/`output_schema` are themselves valid draft-2020-12 schemas (AC1). Raises a domain error on failure.
  - [ ] T2.2 `validate_instance(schema: dict, instance: dict) -> list[str]` -- validates a payload against a schema, returning a list of human-readable error strings (empty = valid). Used for input (AC2) and output (AC3) validation. Confirm `jsonschema` is pinned in stack.md / `pyproject.toml`; add it as a dependency if the Draft202012Validator is not already available (flag as Open Question).
- [ ] **T3 -- Sandbox adapter implementing `SandboxPort` (AR-14)** (AC: #4, #5)
  - [ ] T3.1 `app/core/adapters/sandbox.py` (NEW) -- `SubprocessSandbox` implementing the existing `SandboxPort` Protocol (`run(code, stdin="", *, timeout_s=10, memory_mb=128) -> SandboxResult`). Do NOT redefine the port -- it already exists at `app/core/ports/sandbox.py`.
  - [ ] T3.2 Launch embedded Python in a **child subprocess** (`subprocess` / `resource`-limited exec), passing the Tool input as JSON via **stdin**, reading result JSON from **stdout** (AC4). Parse stdout JSON into `SandboxResult.output`.
  - [ ] T3.3 Enforce AR-14 caps: **no network egress** (block sockets -- e.g. run with no network namespace / seccomp / a socket-denying preexec, per the platform's chosen mechanism), **restricted builtins** (strip dangerous builtins/`__import__` of network + fs-escape modules), **10s CPU cap** (`resource.setrlimit(RLIMIT_CPU, ...)` or wall-clock kill), **128MB memory cap** (`RLIMIT_AS`). Input via stdin, output via stdout only.
  - [ ] T3.4 On timeout -> terminate the subprocess, set `SandboxResult.timed_out=True`, non-zero `exit_code`. On memory breach -> the OS kills the child; surface as a non-zero exit / violation. These map to AC5 `tool.sandbox_violation` at the ToolPort layer (T4).
  - [ ] T3.5 Portability note: `resource.setrlimit` is POSIX-only; the dev host is Windows. Gate the hard rlimits behind a POSIX check and provide a documented fallback (e.g. run the sandbox only in the Linux container / CI, or a `psutil`-based memory/CPU watchdog on Windows). Flag the chosen approach as an Open Question if it affects local dev.
- [ ] **T4 -- Tool invocation service implementing `ToolPort`** (AC: #2, #3, #4, #5)
  - [ ] T4.1 `app/modules/agent_builder/tool_service.py` (NEW) -- `AgentToolPort` implementing the existing `ToolPort` Protocol (`invoke(name, arguments, *, tenant_id, department_id) -> ToolOutput`). Do NOT redefine the port -- it exists at `app/core/ports/tool.py`.
  - [ ] T4.2 Load the Tool record (RLS-scoped by tenant); validate `arguments` against `input_schema` (T2.2). On failure -> return `ToolOutput(success=False, error=...)` (structured error to the Orchestrator) AND `audit.log(type="tool.rejected")` (AC2).
  - [ ] T4.3 On valid input, `audit.log(type="tool.invoked")`, then route: `embedded_python` present -> `SandboxPort.run(code, stdin=json(arguments))` (AC4); else MCP-routed -> `McpClientPort.call_tool(name, arguments, tenant_id=..., department_id=...)` (AD-3, keyword-only AD-11 scope). Do NOT branch on a concrete adapter import -- depend on the ports.
  - [ ] T4.4 Validate the raw output against `output_schema` (T2.2). On failure -> reject (return `ToolOutput(success=False, ...)`) + `audit.log(type="tool.rejected")` for the output-schema failure (AC3).
  - [ ] T4.5 On sandbox timeout/memory breach (`SandboxResult.timed_out` or violation exit) -> `audit.log(type="tool.sandbox_violation")` and return a structured failure (AC5).
  - [ ] T4.6 Every `audit.log()` call goes through the injected `AuditPort` (`PostgresAuditSink`) -- never direct SQL to `audit_trail` (AD-4). Populate `AuditEntry` FR-21 fields; `input`/`output` carry tool name + validation summary, NOT the raw `header` auth secret.
- [ ] **T5 -- Tool CRUD + Test-Tool routes** (AC: #1, #7)
  - [ ] T5.1 `app/modules/agent_builder/routes.py` (UPDATE) -- `POST /agents/{agent_id}/tools` registers a Tool: body `{display_name, header, input_schema, output_schema, embedded_python?}`; validates both schemas as draft-2020-12 (T2.1) -> `422`/structured error on invalid schema; returns `201` with `{tool_id (UUID v7), agent_id, display_name, created_at}` (header/auth NOT echoed in full). Requires builder role + Agent authz (reuse Story 2-1 guards). Emits an `audit.log(type="tool.created")` if the module convention logs CRUD (align with Story 2-1 AC8).
  - [ ] T5.2 `GET /agents/{agent_id}/tools` (list, RLS-scoped, header masked), `PATCH /agents/{agent_id}/tools/{tool_id}`, `DELETE .../tools/{tool_id}` (soft-delete) -- mirror the Story 2-1 CRUD/authz/soft-delete conventions.
  - [ ] T5.3 `POST /agents/{agent_id}/tools/{tool_id}/test` -- the "Test Tool" endpoint (AC7): accepts `{sample_input}`, runs the SAME `AgentToolPort.invoke` path (input-validate -> sandbox|MCP -> output-validate), returns the structured `ToolOutput` (success + output OR the validation/sandbox error). This still emits the normal `tool.invoked`/`tool.rejected`/`tool.sandbox_violation` audit entries so test runs are traceable.
- [ ] **T6 -- Frontend: Tools tab** (AC: #6, #7)
  - [ ] T6.1 `frontend/src/lib/toolsApi.ts` (NEW) -- typed `apiFetch` wrappers: `listTools(agentId)`, `createTool(agentId, input)`, `updateTool(agentId, toolId, patch)`, `deleteTool(agentId, toolId)`, `testTool(agentId, toolId, sampleInput)`. Reuse `apiFetch` (JWT + tenant headers + envelope unwrap; Story 1.4/1.8). TS types for `Tool`, `CreateToolInput`, `ToolTestResult`.
  - [ ] T6.2 `frontend/src/hooks/useAgentTools.ts` (NEW) -- TanStack Query hooks (`useQuery ["agent-tools", agentId]`, mutations invalidating that key), mirroring `useAgent*` shape from Story 2-2.
  - [ ] T6.3 `frontend/src/components/agents/tabs/ToolsTab.tsx` (REPLACE the Story 2-2 placeholder) -- list registered Tools (display_name, kind = MCP|Embedded Python badge, last-modified); "New Tool" Primary CTA (UX-DR3); per-row edit/delete. Empty/loading/error states per UX-DR23. Tools-tab badge count wires into Story 2-8's tab-count.
  - [ ] T6.4 `frontend/src/components/agents/ToolEditor.tsx` (NEW) -- form: `display_name`, `header` (auth field masked, UX-DR8), two **monaco-editor** JSON Schema editors for `input_schema` / `output_schema` with **live client-side validation** (UX-DR7 code block; parse + draft-2020-12 lint, show inline errors), optional `embedded_python` code editor. Reuse Story 2-2 dirty/toast/confirm machinery. Respect the single-Primary-CTA rule.
  - [ ] T6.5 "Test Tool" affordance (AC7) -- a panel to enter `sample_input` JSON, call `testTool`, and render the returned output OR the structured validation/sandbox error (AC7). Loading/error states per UX-DR23.
  - [ ] T6.6 monaco-editor integration -- if monaco is not yet a frontend dependency, add it (or an equivalent JSON code editor with schema linting) and lazy-load it so it does not bloat the initial bundle. Flag the dependency choice as an Open Question. lucide `semanticIcons.Tool` for the tab/badge.
- [ ] **T7 -- Tests (backend)** (AC: #1-#5)
  - [ ] T7.1 `backend/tests/unit/test_schema_validation.py` -- valid draft-2020-12 schema accepted; malformed schema rejected (AC1); instance validation returns errors for a mismatched payload, empty for a valid one.
  - [ ] T7.2 `backend/tests/unit/test_tool_service.py` -- input mismatch -> `ToolOutput(success=False)` + one `audit.log(type="tool.rejected")`, and `SandboxPort`/`McpClientPort` NEVER called on rejection (AC2). Valid input -> `tool.invoked` logged then routed (AC2/AC4).
  - [ ] T7.3 `backend/tests/unit/test_tool_service.py` -- output failing `output_schema` -> rejected + `tool.rejected` audit (AC3).
  - [ ] T7.4 `backend/tests/unit/test_sandbox.py` -- **sandbox timeout test**: an embedded script that spins > 10s CPU is terminated, `timed_out=True`, and the service logs `type="tool.sandbox_violation"` (AC5). **Memory-breach test**: a script allocating > 128MB is killed and surfaces as a violation (AC5). **No-network test**: a script attempting an outbound socket fails inside the sandbox (AR-14). stdin-in/stdout-out round-trip (AC4). Gate POSIX-rlimit assertions per T3.5.
  - [ ] T7.5 `backend/tests/unit/test_ports.py` (extend) -- `SubprocessSandbox` satisfies `isinstance(obj, SandboxPort)`; `AgentToolPort` satisfies `isinstance(obj, ToolPort)` (structural compliance).
  - [ ] T7.6 Route tests -- `POST /agents/{id}/tools` returns `201` + UUID v7 `tool_id`; invalid schema -> structured error; header/auth not echoed; `POST .../test` returns structured output. Use fakes for `SandboxPort`/`McpClientPort`/`AuditPort` (no real MCP server -- AD-3; no real subprocess where the test only checks routing).
- [ ] **T8 -- Tests (frontend)** (AC: #6, #7)
  - [ ] T8.1 `ToolsTab.test.tsx` -- list renders, empty/loading/error states, "New Tool" opens editor.
  - [ ] T8.2 `ToolEditor.test.tsx` -- invalid JSON schema shows inline validation error (AC6); masked auth field; save fires `createTool`/`updateTool` + success toast; dirty dot on edit.
  - [ ] T8.3 Test-Tool test -- sample input -> `testTool` called; success output rendered; structured error rendered on failure (AC7). Mock `toolsApi`/`apiFetch` (no live network).
- [ ] **T9 -- Verify** (AC: all)
  - [ ] T9.1 Backend: `uv run pytest -v` green; `uv run ruff check app tests` clean; no function > 50 lines.
  - [ ] T9.2 Frontend: `npx tsc --noEmit` clean; `npx vitest run` green; `npm run build` succeeds.
  - [ ] T9.3 DoD evidence: cite the passing sandbox timeout + memory-breach tests and the input/output rejection tests by file:line.

## Dev Notes

### Scope Boundaries -- CRITICAL

**Story 2.6 delivers Tool *registration* + JSON Schema *validation* + embedded-Python *sandbox execution* + a *Test-Tool* affordance. It does NOT deliver the runtime dispatch loop that actually calls Tools during a Workflow Run -- that is Epic 3.**

Do:
- Persist Tools against an Agent (`tools` table, RLS-scoped) with `{display_name, header, input_schema, output_schema, embedded_python?}` and a UUID v7 `tool_id`.
- Validate submitted schemas as JSON Schema **draft 2020-12** at registration; validate input/output on invocation.
- Implement the `SandboxPort` adapter (AR-14 subprocess sandbox) and the `ToolPort` invocation service that routes to sandbox (embedded Python) or MCP.
- Build the Tools tab UI (monaco JSON Schema editor + live validation) and the Test-Tool affordance.
- Log `tool.invoked` / `tool.rejected` / `tool.sandbox_violation` through the audit sink.

Do NOT:
- Implement the Orchestrator / Workflow Run loop that dispatches Tool calls (Epic 3). This story only builds the invocation *path* and exposes it via the `ToolPort`; the Orchestrator wiring is Epic 3.
- Redefine `ToolPort` or `SandboxPort` -- both already exist as Protocols from Story 1.4. Provide the concrete adapters/services only.
- Build the API Integrations feature -- that is **Story 2.7** (`header` here may reference an integration later, but this story does not build the integrations tab).
- Build the MCP **server** or a real `rag.search`/tool -- VAIC is an MCP client (AD-3).
- Re-implement auth/RLS/error envelope/audit sink -- reuse the Epic 1 (DONE) contracts.

### Dependencies -- CRITICAL

- **Story 2-1 (Agent record + `agent_builder` module)** -- Tools are registered *against* an Agent; `Tool.agent_id`/`tenant_id`/`department_id` derive from the Agent record. The `agents` table, RLS pattern, builder-role authz guards, soft-delete convention, and `audit.log(type="agent.*")` CRUD pattern are delivered by 2-1 and reused verbatim. The `tools` migration's `down_revision` is the `agents` migration head -- confirm the exact revision at implementation time (2-1 may not be merged at baseline).
- **Story 2-2 (Agent detail shell + Tools tab placeholder)** -- this story REPLACES the `ToolsTab` "Coming soon" placeholder (`frontend/src/components/agents/tabs/ToolsTab.tsx`) with the real Tools tab, reusing 2-2's dirty-dot / Toast / ConfirmDialog / `apiFetch` / TanStack Query conventions. UX-DR16 Tools tab lives in the 6-tab nav 2-2 built.
- **Story 1.4 (Core ports)** -- `ToolPort` (`app/core/ports/tool.py`), `SandboxPort` (`app/core/ports/sandbox.py`), `AuditPort` (`app/core/ports/audit.py`), `McpClientPort` all exist as `@runtime_checkable` Protocols. This story provides the concrete `SandboxPort`/`ToolPort` implementations (both were defined-but-not-implemented in 1.4).
- **Epic 3 (consumer)** -- Tool *invocation during a Workflow Run* (epics.md L785) is executed by the Orchestrator in Epic 3. This story builds and unit-tests the invocation path and exposes it via `ToolPort`; it does not wire the Run loop.

### Architecture Compliance

- **AR-14 (Embedded-Python sandbox rules)** -- The single most important invariant for the sandbox. Embedded Python executes in a **subprocess only**, with **NO network egress**, **restricted builtins**, a **10-second CPU cap**, and a **128MB memory cap**. Input is passed via **stdin**, output read from **stdout**. Auth/stored credentials in `header` are stored (encrypted/at-rest per the platform convention), never hard-coded and never logged. [Source: backend/app/core/ports/sandbox.py L1-9, L37-47; epics.md L788-791]
- **`SandboxPort` contract (Story 1.4)** -- `run(code: str, stdin: str = "", *, timeout_s: int = 10, memory_mb: int = 128) -> SandboxResult`; `SandboxResult{stdout, stderr, exit_code, timed_out, truncated, output}`. The adapter must set `timed_out=True` on the 10s breach and surface memory kills as a non-zero exit. [Source: backend/app/core/ports/sandbox.py L20-68]
- **`ToolPort` contract (Story 1.4)** -- `invoke(name, arguments, *, tenant_id, department_id) -> ToolOutput`; `ToolPort` "routes to `McpClientPort` or `SandboxPort` based on the Tool's configuration" -- exactly the embedded-Python-vs-MCP branch this story implements. `ToolOutput{tool_name, output, success, error, latency_ms}` is the structured result/error returned to the Orchestrator (AC2). [Source: backend/app/core/ports/tool.py L1-9, L21-67]
- **JSON Schema draft 2020-12** -- Both submitted schemas are validated as draft-2020-12 documents at registration (AC1), and used to validate instances on invocation (AC2/AC3). Use `jsonschema.Draft202012Validator.check_schema` for the schema-of-schemas check and `Draft202012Validator(schema).iter_errors(instance)` for instance validation. [Source: epics.md L784, L786-787]
- **AD-4 (Single audit sink, append-only)** -- All `tool.invoked` / `tool.rejected` / `tool.sandbox_violation` entries go through `AuditPort.log` (`PostgresAuditSink`) only. `audit_trail` is INSERT-only (UPDATE/DELETE revoked). An `audit.log()` failure crashes the calling Run -- never swallow. Never write `audit_trail` directly. [Source: backend/app/core/ports/audit.py L1-12, L53-68]
- **AD-3 (MCP client)** -- MCP-routed Tools invoke `McpClientPort.call_tool(name, arguments, tenant_id=..., department_id=...)`; VAIC never runs the MCP server. [Source: backend/app/core/ports/tool.py L4-8]
- **AD-11 (Client-side tenant/department scope)** -- `ToolInvocation`/`invoke` carry keyword-only `tenant_id` + `department_id`; MCP calls are scoped client-side (raise before the network on mismatch). Tool records are RLS-scoped by `tenant_id`. [Source: backend/app/core/ports/tool.py L21-27, L48-56]
- **AD-1 (Hexagonal)** -- `SubprocessSandbox` lives in `core/adapters/`, `AgentToolPort` in `modules/agent_builder/`; both depend on ports, never on concrete sibling adapters. Do not `import` a concrete MCP/anthropic adapter from module code.
- **AD-2 / Story 1.2 (RLS)** -- The `tools` table gets `ENABLE`+`FORCE ROW LEVEL SECURITY` + tenant-isolation policy + `REVOKE DELETE` (soft-delete-only), mirroring `agents`/`audit_trail`.
- **Function size**: keep all functions under 50 lines (project convention, per Story 1.4 DoD).

### UX Compliance

- **UX-DR16 (Agent Builder Surface -- Tools tab)** [epics.md L233] -- The Tools tab is one of the locked 6 tabs (2-2). This story fills it with the Tool list + editor + Test-Tool affordance. Tools-tab badge count ("N tools") is finalized in Story 2-8; expose the count here.
- **UX-DR7 (Code / JSON block)** -- The JSON Schema editors render as code blocks (monaco-editor or equivalent) with syntax highlighting + live validation; reuse `CodeBlock` styling tokens where sensible.
- **UX-DR8 (Form patterns)** -- Labels above inputs, required `*` in destructive color, validate on blur, inline errors. The `header` auth field is masked (never display the full stored secret).
- **UX-DR23 (Empty / Loading / Error)** -- Tools list, editor load, and Test-Tool result each define empty/skeleton/error states; no silent failures. Follow the `RecentRuns.tsx` branch order.
- **UX-DR3 (Buttons)** -- one Primary CTA per view ("New Tool" on the list, "Save" in the editor).
- **UX-DR9 (Motion)** -- reuse Toast (280ms) / ConfirmDialog (200ms) from Story 2-2; only transform/opacity animate; respect `prefers-reduced-motion`.
- **UX-DR10/DR11 (Icons)** -- `semanticIcons.Tool` (lucide-react, 1.5px stroke); no new icon library.

### File Structure Changes

```
backend/
├── app/
│   ├── core/
│   │   └── adapters/
│   │       └── sandbox.py                      # NEW -- SubprocessSandbox implements SandboxPort (AR-14)
│   └── modules/
│       └── agent_builder/
│           ├── models.py                       # UPDATE -- add Tool(Base) model (tools table)
│           ├── routes.py                       # UPDATE -- POST/GET/PATCH/DELETE tools + POST .../test
│           ├── schema_validation.py            # NEW -- draft-2020-12 schema + instance validation
│           └── tool_service.py                 # NEW -- AgentToolPort implements ToolPort (route + validate + audit)
│   └── alembic/versions/
│       └── XXXX_create_tools_rls.py            # NEW -- tools table + RLS + soft-delete grants
└── tests/unit/
    ├── test_schema_validation.py               # NEW
    ├── test_tool_service.py                    # NEW -- input/output reject + audit + routing
    ├── test_sandbox.py                         # NEW -- timeout, memory-breach, no-network, stdin/stdout
    └── test_ports.py                           # UPDATE -- SubprocessSandbox / AgentToolPort structural compliance

frontend/
└── src/
    ├── lib/toolsApi.ts                         # NEW -- apiFetch wrappers (list/create/update/delete/test)
    ├── hooks/useAgentTools.ts                  # NEW -- TanStack Query hooks
    └── components/agents/
        ├── tabs/ToolsTab.tsx                   # REPLACE Story 2-2 placeholder -- real Tools tab
        └── ToolEditor.tsx                      # NEW -- monaco JSON Schema editors + Test-Tool panel
```

Reference (unchanged, cited): `backend/app/core/ports/tool.py`, `backend/app/core/ports/sandbox.py`, `backend/app/core/ports/audit.py`, `backend/app/core/ports/mcp_client.py`, `backend/app/modules/agent_builder/{models,routes,service}.py` (Story 2-1), `frontend/src/lib/api.ts`, `frontend/src/components/agents/AgentDetailShell.tsx` (Story 2-2).

### Testing

- **Backend**: `pytest` + `uv run pytest`; `ruff` clean. Use fakes for `AuditPort`, `McpClientPort`, and (for routing tests) `SandboxPort` -- assert the right port is called and the right audit `type` is emitted; assert the *other* port is NOT called on rejection.
- **Mandatory sandbox tests** (AC5/AR-14): (1) **timeout** -- a > 10s-CPU script terminates with `timed_out=True` and yields a `tool.sandbox_violation` audit entry; (2) **memory breach** -- a > 128MB allocation is killed and surfaces as a violation; (3) **no-network** -- an outbound socket attempt fails inside the sandbox. These exercise the real `SubprocessSandbox`, gated per T3.5 for the POSIX-only rlimits (run in the Linux container / CI if the dev host is Windows).
- **Validation tests** (AC1/AC2/AC3): malformed schema rejected at registration; input mismatch -> `tool.rejected` + no downstream call; output-schema failure -> `tool.rejected`.
- **Frontend**: Vitest + Testing Library. Mock `toolsApi`/`apiFetch` (no live network). Test live JSON-schema validation error display, masked auth field, save payload shape, and the Test-Tool success/error render.
- **Stack is pinned** [Source: stack.md] -- no web research. Backend: Python 3.13, FastAPI, SQLAlchemy 2.x, Pydantic 2.x, `jsonschema` (confirm/add). Frontend: React 19, Vite 8, TS 7.x, Tailwind 4, TanStack Query, Vitest, monaco-editor (confirm/add).

### Anti-Patterns to Avoid

1. **Do NOT run embedded Python in-process or via `eval`/`exec` in the main process.** AR-14 mandates a **subprocess** with rlimits + no network + restricted builtins. In-process execution voids every sandbox guarantee.
2. **Do NOT allow network egress from the sandbox** -- no `requests`, no sockets, no DNS. A Tool that needs an external call must go through an API Integration (Story 2.7) / MCP, not the sandbox.
3. **Do NOT skip the schema-of-schemas check.** AC1 requires the *submitted schemas themselves* to be valid draft-2020-12 documents (`check_schema`), not just that instances validate.
4. **Do NOT return unvalidated output as success.** Output must pass `output_schema` before it reaches the Orchestrator (AC3); a failing output is a `tool.rejected`, not a success.
5. **Do NOT swallow the sandbox violation.** A timeout/memory breach MUST emit `tool.sandbox_violation` and return a structured failure -- never silently return partial stdout.
6. **Do NOT log the `header` auth secret** to `audit_trail` or echo it to the client. Store it; return/log only metadata (NFR-9 / AR-14 stored credentials).
7. **Do NOT redefine `ToolPort` / `SandboxPort`.** They are Protocols from Story 1.4 -- implement, don't re-declare.
8. **Do NOT write `audit_trail` directly.** Only via `AuditPort.log` (AD-4).
9. **Do NOT implement the Orchestrator dispatch loop here.** Build + expose the invocation path via `ToolPort`; Epic 3 wires the Run.
10. **Do NOT hard-code the `tools` migration `down_revision`** before confirming the Story 2-1 `agents` migration head.

### References

- [Source: epics.md#Story-2.6 L773-793] Story statement + ACs verbatim (register L781-784, input/output validation L785-787, sandbox AR-14 L788-791, monaco editor L792, Test Tool L793).
- [Source: epics.md#Story-2.1 L662-682] Agent record + `agent_builder` module + RLS/authz/soft-delete/audit conventions (dependency).
- [Source: epics.md#Story-2.2 L684-707] Detail shell + 6-tab nav + Tools tab placeholder + dirty/toast/confirm conventions (dependency).
- [Source: epics.md#Story-2.7 L795-814] API Integrations (the `header`/auth integration this story does NOT build).
- [Source: epics.md L233] UX-DR16 Agent Builder Surface -- Tools tab.
- [Source: backend/app/core/ports/tool.py L1-67] `ToolPort.invoke`, `ToolInvocation`, `ToolOutput`; MCP-vs-embedded-Python routing.
- [Source: backend/app/core/ports/sandbox.py L1-68] `SandboxPort.run` + `SandboxResult`; AR-14 no-network / restricted-builtins / 10s CPU / 128MB / stdin-stdout.
- [Source: backend/app/core/ports/audit.py L1-68] `AuditEntry` FR-21 fields + `AuditPort.log` (AD-4, append-only, crash-on-failure).
- [Source: backend/app/core/ports/mcp_client.py] `McpClientPort.call_tool` (AD-3 / AD-11).
- [Source: _bmad-output/implementation-artifacts/1-4-core-ports-api-error-envelope.md L26, L45-47, L179-181] `ToolPort`/`SandboxPort` defined-not-implemented in Story 1.4.
- [Source: prd FR-3] Tool input/output schema validation + structured rejection.
- [Source: prd FR-21] Per-step audit trail logging.
- [Source: prd NFR-9] Never log secrets / banking data sensitivity.
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AR-14] Embedded-Python sandbox rules.
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-3] MCP client.
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-4] Single audit sink, append-only.
- [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-11] Client-side tenant/department scope.
- [Source: ARCHITECTURE-SPINE/stack.md] Pinned stack -- no web research.

## Dev Agent Record

### Agent Model Used

### Debug Log References

### Completion Notes List

### File List

## Change Log

- 2026-07-17: Story 2.6 spec authored by story-context engine. Status: ready-for-dev.
