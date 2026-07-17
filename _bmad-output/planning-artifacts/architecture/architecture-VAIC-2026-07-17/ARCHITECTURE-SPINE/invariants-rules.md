# Invariants & Rules

## AD-1 — Paradigm: Hexagonal Modular Monolith

- **Binds:** all
- **Prevents:** one builder going layered, another microservices, divergence on where domain logic lives
- **Rule:** System is one FastAPI process composed of the six bounded modules in `modules/`. Domain logic lives at each module's center; HTTP routes, DB access, LLM calls, MCP tool invocations, and sandbox execution are ports/adapters and never contain domain decisions. Cross-module calls go through a module's public service interface, never its internal models.

## AD-2 — Multi-tenant isolation at the data layer via Postgres RLS

- **Binds:** FR-25, every persisted write
- **Prevents:** one module filtering `tenant_id` at the API, another at the ORM, another forgetting — cross-tenant leak via a single missed filter
- **Rule:** Every table carries `tenant_id UUID NOT NULL`. Postgres Row-Level Security policies enforce `tenant_id = current_setting('app.tenant_id')` on every row. FastAPI middleware sets the session variable per request from the authenticated user. Application code never filters tenant_id manually. Only the bootstrap script and migrations run with `BYPASSRLS`. [ADOPTED — PRD FR-25 + banking audit obligation make this load-bearing.]

## AD-3 — MCP is the external-tool protocol; Task state is VAIC-internal Postgres

- **Binds:** FR-3, FR-9 (reconciled)
- **Prevents:** coupling VAIC to an MCP server it doesn't own; confusion about where Task state lives
- **Rule:** VAIC is an MCP **client**. Tools owned by the parallel-team MCP server (`rag.search`, `gmail.send`, `calendar.write`, future tools) are invoked through `McpClientPort`. **The MCP server itself is out of scope — VAIC does not build, host, or own it.** Orchestrator-to-Specialist-Agent Task dispatch is an internal domain operation: Task rows live in the `tasks` Postgres table, claimed and completed by the orchestrator's worker loop. The PRD's "MCP doubles as Task Store" is relaxed for MVP. *(Reconciliation: PRD FR-9 and §9 contradict this — see Open Questions.)*

## AD-4 — Single audit sink; append-only at the schema level; failure crashes the Run

- **Binds:** FR-21, all modules
- **Prevents:** one module writing `audit_trail` via raw SQL, another via ORM, another skipping it — broken traces that fail SM-4; silent entry loss when Postgres hiccups
- **Rule:** `audit.log(entry)` in `core/ports/audit.py` is the only path to write `audit_trail`. Every Workflow Run step — Orchestrator decomposition, Task dispatch, Agent retrieval, Tool call, Model invocation (with model name + latency), aggregation, escalation, Mini-App emission — MUST call it. The `audit_trail` table grants `INSERT` only to the app role; `UPDATE` and `DELETE` are revoked. Append-only is enforced at the DB, not just by convention. **If an `audit.log()` call fails (DB down, constraint violation), the calling Workflow Run transitions to `failed` — never silently drop an entry.** This honors PRD counter-metric SM-C1: trace completeness outranks Run completion.

## AD-5 — Visibility Tier enforced at the row level on `mini_app_rows`

- **Binds:** FR-14, FR-15, FR-16
- **Prevents:** API-layer gating that the auto-generated UI or a future bulk-import path bypasses
- **Rule:** RLS policies on `mini_app_rows` encode the access matrix (PRD addendum §A3) using `visibility_tier`, `department_id`, and a whitelist check. The auto-generated CRUD endpoints, the React UI, and any future path inherit the same gating because they all read rows through SQL. No client-side or API-only gating.

## AD-6 — Persisted state machines with compare-and-set on every transition

- **Binds:** FR-7, FR-8, FR-9, FR-10
- **Prevents:** in-memory run state lost on process restart; two Specialist Agents racing on the same Task; inconsistent resume and timeout semantics across builders
- **Rule:** Every stateful record (`workflow_runs`, `tasks`, `mini_app_rows`) carries a `status` (or `version`) enum. State transitions are a single `UPDATE ... WHERE id=? AND status=?` **and the application checks `rowcount == 1`** — a zero-row update means another worker won the race and the local attempt aborts cleanly. Specific machines:
  - `workflow_runs.status`: `pending | running | awaiting_human | completed | failed | timed_out`. arq workers poll `pending` on startup and resume. Escalations flip `running → awaiting_human`; the 5-min timeout flips `awaiting_human → timed_out`.
  - `tasks.status`: `pending | claimed | completed | failed`. A Specialist Agent worker claims via `UPDATE ... WHERE status='pending'`; if `rowcount == 0`, another Agent beat it — abandon and pick the next.
  - `mini_app_rows`: see AD-8 — writes carry an optimistic `version` column bumped on every UPDATE; a stale-version write is rejected.

## AD-7 — Model Layer is a port; Agent picks provider+model at config time

- **Binds:** FR-5, FR-26
- **Prevents:** Agent code importing the Anthropic SDK directly while Orchestrator imports OpenAI; provider lock-in against the user's explicit "model is user-configurable" requirement
- **Rule:** `LlmPort` (`complete`, `stream`, `embed`) in `core/ports/llm.py` is the only abstraction agents and the orchestrator may import. Adapters: `anthropic`, `openai`, `google`, `ollama`. The Agent record stores `{provider, model_name, parameters}` as data — never as code. **The platform never fixes the model; it always reads from Agent config.** A missing provider surfaces at run time, logged in `audit_trail`.

## AD-8 — Mini-App schema emission is the only Agent→Provisioner contract; mini_app ownership is single

- **Binds:** FR-12, FR-13, FR-14, FR-15, FR-17
- **Prevents:** Agent emitting ad-hoc shapes; Provisioner growing module-specific branches; ambiguous ownership of `mini_app_rows` between the auto-gen CRUD endpoints and Agent-initiated writes
- **Rule:** Mini-App emission is a JSON document validated against the schema-meta-schema before persistence. The Provisioner is a function `(tenant_id, department_id, owner_id, valid_schema, initial_rows?) -> (namespace + CRUD endpoints + UI)`. It creates the namespace AND the initial row(s) **atomically in one DB transaction** (the PRD §A6 example — "one row carrying the consolidated decision" — flows through this path). After provisioning, **the `mini_app` module's auto-generated CRUD endpoints are the sole writers to `mini_app_rows`.** Specialist Agents never write to `mini_app_rows` directly post-provisioning; if a Run needs to update a row, it routes through the same CRUD endpoints. App Event emission (AD-9) fires from those endpoints, not from Agent code.

## AD-9 — App Events flow only through the Action Bus

- **Binds:** FR-17, FR-19, FR-20
- **Prevents:** Mini-App writing directly to a Workflow Run; bypass of sequence numbering and at-least-once guarantees
- **Rule:** Mini-App row changes (create / update / delete) emit App Events onto the Action Bus (an arq queue). Event Triggers subscribe via filter expressions. Workflow Runs start only via: (a) explicit user action, (b) Schedule Trigger, or (c) Event Trigger match. No direct Mini-App → Workflow Run call paths.

## AD-10 — Tenant context is materialized in job payloads and re-set at worker entry

- **Binds:** all background work — FR-9 (Workflow Run execution), FR-18 (Schedule Triggers), FR-19 (Event Triggers)
- **Prevents:** the classic Python async footgun where a `contextvars.ContextVar` set by FastAPI middleware dies at the arq worker process boundary — every background Run would crash on RLS or leak across tenants
- **Rule:** `tenant_context` is set by FastAPI middleware on HTTP paths (Convention). For every background job enqueued (Workflow Run, Event Trigger fan-out, Schedule Trigger fan-out), the enqueuer MUST capture `tenant_id` (and `department_id` if relevant) from the current context and serialize it into the arq job kwargs. The arq worker function's first action is to deserialize those fields, set the `contextvars.ContextVar`, and issue `SET LOCAL app.tenant_id` on its DB connection before any domain work. **Schedule Triggers fire without HTTP context**: the arq `cron_jobs` entrypoint runs a single job that (i) enumerates all tenants with matching schedules (under `BYPASSRLS`), (ii) for each tenant enqueues a per-tenant Run job with that tenant's `tenant_id` materialized in the payload. Never assume a worker inherits context from anywhere.

## AD-11 — Client-side department scope on every MCP call

- **Binds:** FR-2 (reconciled), FR-3, FR-6
- **Prevents:** AD-2's RLS cannot reach the parallel-team MCP server — without an explicit rule, a Credit Agent's `rag.search` could retrieve HR-department documents, silently breaking the PRD's department-isolation guarantee
- **Rule:** Every `McpClientPort` call MUST include `tenant_id` and `department_id` as parameters (or a derived `namespace_token` the parallel team agrees to honor). VAIC's `McpClientPort` implementation **enforces client-side** that the parameters match the calling Agent's `department_id`; a mismatched call raises before it hits the network. The MCP server is trusted to honor the scope; if it doesn't, that's the parallel team's defect, but VAIC never sends an unscoped call. This is the only mechanism standing behind PRD FR-2's department-isolation consequence while retrieval is outsourced.
