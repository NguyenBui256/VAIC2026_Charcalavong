# Divergence 1 — Tenant Contextvar Does Not Survive the arq Worker Boundary

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
