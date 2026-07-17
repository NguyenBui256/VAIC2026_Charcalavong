# Adversarial Divergence Review — VAIC Architecture Spine

**Reviewer lens:** Construct two units one level down that each obey every AD to the letter yet still build incompatibly. Every pair found is a hole to close.

**Date:** 2026-07-17

---

## Verdict: PASS-WITH-WARNINGS

The spine's nine ADs close the most visible architectural seams. However, eight specific divergence pairs exist where two independently compliant units produce conflicting data shapes, dual-ownership races, or silently broken cross-boundary assumptions. Five are HIGH or CRITICAL and must be closed before the build begins.

---

## Divergence 1 — Tenant Contextvar Does Not Survive the arq Worker Boundary

**Severity:** CRITICAL

**Unit A:** FastAPI request handler in the `orchestrator` module. It calls `tenant_context.set(tenant_id)` via middleware (Convention: "Tenant context") and then enqueues a background Run via `arq.enqueue_job("run_workflow", run_id)`.

**Unit B:** The arq worker process picks up `run_workflow(run_id)`. It calls `orchestrator.service.decompose(run_id)`, which internally calls domain logic that reads `tenant_context.get()`.

**AD each obeys:**
- AD-1: Both go through module service interfaces; domain logic is at the center.
- AD-6: Both use the persisted state machine for Run status transitions.
- Convention "Tenant context": "Domain code reads `tenant_context.get()`; never pass `tenant_id` as a function argument."

**Where they diverge:** The Convention says domain code reads `tenant_context.get()` and forbids passing `tenant_id` as a function argument. But `contextvars.ContextVar` is set inside FastAPI middleware within the web process. The arq worker is a separate process — it never runs that middleware. When the worker calls domain code that reads `tenant_context.get()`, it gets a `LookupError` (or `None`), and the RLS session variable is never set on the worker's DB connection. Every query in the worker either crashes or (worse) runs with `app.tenant_id` unset, which means RLS policies either reject all rows or, if the policy has a fallback, leak across tenants.

This is the single most dangerous divergence in the spine. It silently breaks every background Run.

**Proposed fix:** Add a new Convention row and tighten AD-6.

**New Convention row:**

> **Worker tenant bootstrap:** arq job functions MUST call `tenant_context.set(run.tenant_id)` as their first statement, loading `tenant_id` from the `workflow_runs` row by `run_id` *before* any domain call. The DB session's RLS variable must be set from the same var. This is the one sanctioned place where `tenant_id` is read from a row rather than from middleware context.

**Tighten AD-6 — add Rule:**

> **AD-6 Rule addition:** arq worker entrypoints (`run_workflow`, `execute_schedule`, `process_event_trigger`) must restore tenant context from the relevant persisted record before invoking any domain logic. A Run cannot transition to `running` unless tenant context is set.

---

## Divergence 2 — Schedule Trigger Fires Without Tenant Context

**Severity:** CRITICAL

**Unit A:** `actions/triggers.py` registers an arq `cron_jobs` entry: `cron_jobs=[cron(execute_schedule, hour={9}, minute={0})]`. This fires inside the arq worker process at 09:00.

**Unit B:** The `execute_schedule` function needs to know *which tenant* and *which workflow* to run. It calls `orchestrator.service.start_run(workflow_id)`.

**AD each obeys:**
- AD-9: Schedule Trigger starts a Workflow Run — explicitly listed as valid path (b).
- Convention "Async jobs": "arq only — both Schedule Triggers (via `cron_jobs`) and background Workflow Run execution."

**Where they diverge:** arq's `cron_jobs` mechanism has no notion of tenant context. The cron entry fires as a bare function call with no HTTP request, no middleware, no `contextvar`. The function must enumerate all tenants with matching schedules and start a Run for each — but the spine says nothing about how this enumeration happens or how tenant isolation is maintained during it. If `execute_schedule` queries all tenants' schedules and then starts Runs, it needs to iterate tenants, set context per-tenant, and start each Run within that context. There is no AD or Convention governing this loop.

Additionally, the schedule query itself: does it bypass RLS (to see all tenants' schedules) or does it run with no tenant set (getting zero rows or an error)? The spine is silent.

**Proposed fix:** New Convention row.

**New Convention row:**

> **Schedule trigger tenant fan-out:** `execute_schedule` runs with `BYPASSRLS` to read all due `schedule_triggers` rows, then for each matching row: (1) sets `tenant_context` to that row's `tenant_id`, (2) starts the Workflow Run, (3) clears context. The `BYPASSRLS` scope is limited to the single `SELECT` against `schedule_triggers`; all subsequent operations use normal RLS-scoped connections.

**Tighten AD-9 — add Rule:**

> **AD-9 Rule addition:** Schedule Triggers and Event Triggers that fan out across tenants must set tenant context per-tenant in a loop. No domain logic may execute with tenant context unset. The trigger-enumeration query is the single sanctioned `BYPASSRLS` read path at runtime (distinct from bootstrap/migrations).

---

## Divergence 3 — Dual Ownership of `mini_app_rows`: `mini_app` vs `actions`

**Severity:** HIGH

**Unit A:** `mini_app/routes.py` auto-generated CRUD endpoint `PATCH /apps/{app_id}/rows/{row_id}`. Per AD-5 and AD-8, this endpoint writes to `mini_app_rows` with RLS-enforced visibility tiers.

**Unit B:** `actions/bus.py` processes an App Event and, as part of an Event Trigger's Workflow Run, the Orchestrator dispatches a Specialist Agent that calls a Mini-App CRUD endpoint (or writes directly to `mini_app_rows` via the ORM) to update a row as its task output.

**AD each obeys:**
- Unit A: AD-5 (RLS on `mini_app_rows`), AD-8 (Provisioner generated the endpoints).
- Unit B: AD-6 (Task is part of a Run, state machine governed), AD-9 (Event Trigger started the Run via the Action Bus).

**Where they diverge:** Both units write to the same `mini_app_rows` table for the same logical entity, but with different ownership semantics. Unit A is user-driven (a human editing a row). Unit B is agent-driven (a Specialist Agent modifying a row as task output). The spine doesn't say:
1. Whether Specialist Agents may write to `mini_app_rows` directly or must go through the CRUD endpoint.
2. What happens when a user and an Agent concurrently modify the same row (no optimistic concurrency control is specified).
3. Whether the `mini_app` module or the `orchestrator` module owns the write path for agent-initiated row mutations.

If both paths write directly to the table, there is no single owner. If the agent path must go through the CRUD endpoint, then the endpoint is being called from within a background worker (hitting the same contextvar problem from Divergence 1).

**Proposed fix:** Tighten AD-8 and add a Convention row.

**Tighten AD-8 — add Rule:**

> **AD-8 Rule addition:** `mini_app_rows` has exactly one write owner: the `mini_app` module. Specialist Agents and Orchestrator code that need to modify Mini-App rows must call through the `mini_app` module's public service interface (`mini_app.service.update_row`), not the auto-gen HTTP endpoint and not direct ORM writes. This keeps the write path, RLS scoping, and App Event emission in one place.

**New Convention row:**

> **Optimistic concurrency on `mini_app_rows`:** Every `mini_app_rows` update carries `WHERE id = ? AND updated_at = ?` (compare-and-set on the timestamp). A mismatch returns a 409 conflict. This applies to both user-initiated and agent-initiated writes, preventing silent clobber.

---

## Divergence 4 — Concurrent Specialist Agents Racing on Task Claims

**Severity:** HIGH

**Unit A:** Specialist Agent "Credit" (running in arq worker thread A) polls `tasks` for `status = 'pending' AND agent_id = 'credit-agent-uuid'` and claims a task.

**Unit B:** Specialist Agent "Credit" (running in arq worker thread B, same or different worker process) polls the same query at the same instant and claims the same task.

**AD each obeys:**
- AD-6: Both use the state machine. AD-6 specifies compare-and-set for `workflow_runs.status`.
- AD-3: Task rows live in the `tasks` Postgres table, claimed and completed by the orchestrator's worker loop.

**Where they diverge:** AD-6 specifies compare-and-set for `workflow_runs.status` transitions but says nothing about `tasks.status` transitions. The `tasks` table has its own status lifecycle (`pending | claimed | completed | failed`), but the spine only governs `workflow_runs.status`. Two concurrent agents can both successfully `UPDATE tasks SET status = 'claimed' WHERE id = ? AND status = 'pending'` — the second update is a no-op, but neither agent checks the row count. Even if they do check, the spine doesn't mandate it, so one builder might implement it and another might not. The agent that "lost" the claim proceeds with stale ownership and writes results to a task it doesn't own.

**Proposed fix:** Tighten AD-6.

**Tighten AD-6 — add Rule:**

> **AD-6 Rule addition:** Task claims use the same compare-and-set pattern as Run transitions: `UPDATE tasks SET status = 'claimed', claimed_at = now() WHERE id = ? AND status = 'pending'`. The caller MUST check `rowcount == 1`; a zero rowcount means another agent claimed it — the agent skips that task. No SELECT-then-UPDATE without the compare-and-set guard.

---

## Divergence 5 — MCP Server Department Isolation: Whose Responsibility?

**Severity:** HIGH

**Unit A:** `orchestrator` module calls `McpClientPort.call("rag.search", {"query": "...", "department": "credit"})`. The McpClientPort adapter sends this to the external MCP server.

**Unit B:** The external MCP server receives `rag.search` with `department: "credit"` and returns documents. But AD-3 says "the MCP server itself is out of scope — VAIC does not build, host, or own it." Open Question 5 asks "how does it enforce that a Credit Agent's `rag.search` call can't see an HR department's documents?" but provides no answer.

**AD each obeys:**
- AD-3: VAIC is an MCP client; tools invoked through `McpClientPort`.
- AD-2: RLS enforces tenant isolation at the Postgres layer.

**Where they diverge:** AD-2 guarantees isolation inside VAIC's Postgres. AD-3 explicitly excludes the MCP server from VAIC's scope. No AD bridges the gap. If the MCP server doesn't enforce department isolation (or if the `department` parameter is optional and an Agent omits it), a Credit Agent can retrieve HR documents through `rag.search`. VAIC's RLS is useless here because the data left VAIC's boundary. Two builders could implement the `McpClientPort.call` with completely different assumptions: one always passes `department`, the other doesn't. Both comply with AD-3.

**Proposed fix:** New AD.

**New AD-10 — MCP Tool calls must carry department scope; VAIC enforces client-side**

> - **Binds:** FR-3, FR-6, AD-3
> - **Prevents:** cross-department data leakage through MCP tools that VAIC's RLS cannot reach
> - **Rule:** Every `McpClientPort.call` MUST include the calling Agent's `department_id` as a parameter (or in a tool-call header if the MCP protocol supports it). The `McpClientPort` adapter enforces this: if the caller does not supply `department_id`, the adapter raises a `DomainError`. VAIC cannot control what the MCP server does with it, but VAIC guarantees it always sends the scope. This is a client-side guard, not a substitute for server-side enforcement — Open Question 5 remains with the parallel team.

---

## Divergence 6 — Audit Sink Failure Semantics Are Undefined

**Severity:** MEDIUM

**Unit A:** `orchestrator/service.py` completes a decomposition step and calls `audit.log(entry)` per AD-4. Postgres is up; the entry is appended. The Run continues.

**Unit B:** `mini_app/routes.py` processes a row update and calls `audit.log(entry)` per AD-4. Postgres is temporarily down (connection blip, pool exhaustion). `audit.log()` raises a ` psycopg2.OperationalError`.

**AD each obeys:**
- AD-4: "Every Workflow Run step MUST call `audit.log(entry)`." Both call it.

**Where they diverge:** AD-4 says every step must *call* `audit.log()`. It says nothing about what happens when that call fails. Unit A succeeds because Postgres is up. Unit B fails because Postgres is down. The question: does `audit.log()` swallow the error and continue (dropping the audit entry — violating the "MUST call" intent), or does it propagate (crashing the Run — which might be correct for audit but catastrophic for a hackathon demo)?

The convention "Error handling" says "Never swallow. Never return `None` to mean error." By that rule, `audit.log()` propagates, and the Run crashes on any transient DB error during audit. For a demo environment with a 2-day build timeline, this is likely too aggressive.

**Proposed fix:** Tighten AD-4.

**Tighten AD-4 — add Rule:**

> **AD-4 Rule addition (audit failure semantics):** `audit.log()` uses a dedicated DB connection from a separate pool (not the request's transaction). On failure: (1) write the entry to a Redis list `audit_fallback` with TTL 24h, (2) log a `WARNING`, (3) do NOT propagate the exception to the caller. A background arq job (`drain_audit_fallback`) retries entries from the Redis list into Postgres. This trades strict append-only guarantee for Run resilience during transient DB failures. If both Postgres and Redis are down, the entry is lost — acceptable for MVP, logged at `CRITICAL`.

---

## Divergence 7 — Mini-App Provisioner Purity vs Required Side Effects

**Severity:** MEDIUM

**Unit A:** `mini_app/provisioner.py` implements the pure function from AD-8: `(tenant_id, department_id, owner_id, valid_schema) -> (namespace + CRUD endpoints + UI)`.

**Unit B:** The same Provisioner must mount FastAPI routes for the CRUD endpoints (`POST /apps/{app_id}/rows`, etc.) and register a frontend route for the UI. Route mounting is a side effect on the FastAPI app object. Frontend route registration requires emitting a route file or updating a route registry.

**AD each obeys:**
- AD-8: "The Provisioner is a pure function."

**Where they diverge:** AD-8 claims purity, but the Provisioner's output includes "CRUD endpoints" and "UI" — both of which require side effects to become real (mounting routes, registering UI components). A builder reading AD-8 literally might implement a function that returns a data structure describing the endpoints and UI, leaving the route mounting to the caller. Another builder might interpret "CRUD endpoints" as the Provisioner actually calling `app.include_router()`. Both are valid readings of AD-8's prose. The first leaves dangling metadata; the second violates purity.

**Proposed fix:** Tighten AD-8 with a clarification.

**Tighten AD-8 — add Clarification:**

> **AD-8 Clarification:** "Pure function" means the Provisioner has no I/O side effects (no DB writes, no HTTP calls, no file system writes, no LLM calls) and produces deterministic output for the same input. It returns a `ProvisioningPlan` dataclass containing: the `mini_app` row to insert, the route registration descriptor, and the UI spec. A separate `mini_app/lifecycle.py` module applies the plan: inserts the row, calls `app.include_router()` for CRUD routes, and emits the UI route descriptor for the frontend. The Provisioner computes; the lifecycle module acts. This preserves the purity invariant while acknowledging that side effects exist in a separate, named component.

---

## Divergence 8 — Concurrent Orchestrator Workers Double-Picking a `pending` Run

**Severity:** MEDIUM

**Unit A:** arq worker process 1 starts, polls for `pending` Runs, finds `run_id = abc`, transitions it to `running` via `UPDATE ... WHERE id = 'abc' AND status = 'pending'`.

**Unit B:** arq worker process 2 starts at the same time (e.g., both processes recover from a Redis restart), polls for `pending` Runs, finds the same `run_id = abc` before worker 1's transaction commits, and attempts the same transition.

**AD each obeys:**
- AD-6: Both use compare-and-set: `UPDATE ... WHERE id = ? AND status = ?`. AD-6 explicitly specifies this.

**Where they diverge:** AD-6 specifies the compare-and-set pattern, which is correct. But it doesn't address the **visibility** problem. If worker 1's transaction hasn't committed when worker 2 reads, worker 2 sees the row as still `pending` (depending on isolation level). At `READ COMMITTED` (Postgres default), worker 2's `UPDATE` will block on the row lock until worker 1 commits, then see `rowcount = 0` because the status is no longer `pending`. This is actually fine — *if* the worker checks `rowcount`. But AD-6 doesn't mandate checking `rowcount`. A builder could implement the UPDATE and then proceed to run the workflow regardless of whether the claim succeeded.

This is less severe than Divergence 4 because Postgres' row locking provides some protection, but the spine should be explicit.

**Proposed fix:** Tighten AD-6 (same addition as Divergence 4, generalized).

**Tighten AD-6 — add Rule:**

> **AD-6 Rule addition (claim verification):** Every compare-and-set transition MUST verify `rowcount == 1` before proceeding. A zero `rowcount` means the claim failed (another worker owns it); the caller must abandon the operation. This applies to both `workflow_runs.status` and `tasks.status` transitions. No transition consumer may proceed without verifying the claim.

---

## Dimensions Entirely Silent at This Altitude

The following operational dimensions are not covered by any AD, Convention, or Deferred item. They may be intentionally out of altitude scope, but noting them for completeness:

1. **Deployment topology.** The spine says "one FastAPI process" but the Async Jobs convention says "arq only — background Workflow Run execution." arq runs in a separate process (`arq Worker`). The spine doesn't specify: one web process + one worker process? Multiple workers? How is the FastAPI app shared between them (it isn't — they're different entrypoints)?

2. **Database connection pooling across web vs worker.** SQLAlchemy sync engine with a connection pool — the pool config, pool size, and whether the worker reuses the same engine or creates its own, are unspecified. This interacts with Divergence 1 (tenant context must be set per-connection or per-query in the worker).

3. **Observability beyond audit.** AD-4 covers audit trail (domain events). There is no mention of: structured logging (JSON logs?), metrics (Prometheus?), health checks (/health, /ready), or distributed tracing (OpenTelemetry). For a hackathon demo this is likely fine, but the spine should at least list it as Deferred.

4. **Graceful shutdown and in-flight Run handling.** AD-6 says workers poll `pending` runs on startup. What about shutdown? If a worker is killed mid-Run, the Run stays `running` forever. No timeout or reaper mechanism is defined for stuck `running` Runs. The escalation timeout (5 min) only covers `awaiting_human`, not `running`.

5. **Database migration strategy for Mini-App namespaces.** AD-8 says the Provisioner creates "JSONB namespace + CRUD endpoints." This implies dynamic table or JSONB column creation. If a Mini-App schema changes (new columns), what migrates the existing data? No AD covers Mini-App schema evolution.

6. **MCP client retry and timeout.** AD-3 and Open Question 4 acknowledge MCP outage behavior is undefined, but the spine doesn't set even a default timeout for MCP calls. A hung MCP server will stall a Run indefinitely (no `running` timeout per finding #4 above).

---

## Summary Table

| # | Divergence | Severity | Fix |
|---|-----------|----------|-----|
| 1 | Tenant contextvar lost at arq worker boundary | CRITICAL | New Convention + tighten AD-6 |
| 2 | Schedule trigger fires without tenant context | CRITICAL | New Convention + tighten AD-9 |
| 3 | Dual ownership of `mini_app_rows` | HIGH | Tighten AD-8 + new Convention |
| 4 | Concurrent Specialist Agents racing on Task claims | HIGH | Tighten AD-6 |
| 5 | MCP department isolation unowned | HIGH | New AD-10 |
| 6 | Audit sink failure semantics undefined | MEDIUM | Tighten AD-4 |
| 7 | Provisioner purity vs side effects | MEDIUM | Tighten AD-8 clarification |
| 8 | Worker claim verification not mandated | MEDIUM | Tighten AD-6 |
