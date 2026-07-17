# Consistency Conventions

| Concern | Convention |
| --- | --- |
| Entity IDs | UUID v7 (time-ordered, indexable). Never autoincrement. |
| Timestamps | UTC, ISO 8601 with milliseconds (`2026-07-17T08:34:12.123Z`). Column type `timestamptz`. |
| Tenant context | `contextvars.ContextVar` set by FastAPI middleware after auth on HTTP paths. **For arq background jobs, the worker re-sets the contextvar from materialized `tenant_id` in the job payload** (AD-10). Domain code reads `tenant_context.get()`; never pass `tenant_id` as a function argument. DB layer sets the RLS session variable from the same var. |
| Error shape | `{error: {code: string, message: string, details: object, trace_id: uuid}}` — every API error, no exceptions. |
| API envelope | `{data, error, meta}` per project rules. `meta` carries pagination. |
| Event naming | `domain.event_type` — e.g., `mini_app.row.created`, `workflow.run.completed`, `action.trigger.fired`. |
| Audit entry | `{run_id, step_id, agent_id, ts, type, input, output, latency_ms, model}` — exact field names from PRD §FR-21. |
| File naming | Python `snake_case`; routes `kebab-case`; React components `PascalCase`; CSS `kebab-case`. |
| Function size | **Hard ceiling: 50 lines.** Split before merge if longer. applies to both backend and frontend. |
| Async jobs | arq only — both Schedule Triggers (via `cron_jobs`) and background Workflow Run execution. No Celery, no APScheduler, no background threads for domain work. |
| Embedded Python Tools | Only when a Tool can't be expressed as an MCP tool. Executes in a subprocess: no network, restricted builtins, 10s CPU cap, 128 MB memory. Caller passes input via stdin, reads stdout. [ASSUMPTION — MVP downgrade; production needs WASM via `wasmtime-py` or E2B.] |
| MCP calls | Every `McpClientPort` call carries `tenant_id` + `department_id` matching the calling Agent; client-side raise on mismatch (AD-11). Never send an unscoped MCP call. |
| Background jobs | Tenant context is materialized in job kwargs at enqueue time; the worker re-sets contextvar + DB session var at entry (AD-10). Schedule Triggers fan out per-tenant from a single `cron_jobs` entrypoint. |
| Definition of Done | A feature is not done until (a) tests pass with evidence (test `file:line` + green run output) and (b) code reference (production `file:line`) are visible in the PR. |
| No premature abstraction | Rule of Three before extracting a shared helper or introducing a port. Two call sites is not a pattern. |
| Error handling | Errors propagate via exceptions in domain code; the API boundary translates to the error envelope. Never swallow. Never return `None` to mean error. |
