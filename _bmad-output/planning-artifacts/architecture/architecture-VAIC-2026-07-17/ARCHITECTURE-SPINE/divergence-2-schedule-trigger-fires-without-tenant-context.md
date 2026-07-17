# Divergence 2 — Schedule Trigger Fires Without Tenant Context

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
