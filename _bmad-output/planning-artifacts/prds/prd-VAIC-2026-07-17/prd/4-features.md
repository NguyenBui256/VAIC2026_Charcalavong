# 4. Features

The platform's capability surface is organized into six feature groups. **FRs are numbered globally (FR-1 through FR-32) for stable downstream references.** Each FR lists testable consequences; feature-specific NFRs and open questions live inline.

## 4.1 Agent Builder

**Description:** Lets a user configure a **Specialist Agent** end-to-end — identity, **Knowledge Base**, **Tools**, **API Integrations**, prompt, and **Model** — and persist it as a **Tenant**-scoped record. Realizes UJ-1 (steps 1–5). Per-Agent **KB** isolation enforces department-scoped access. The platform never fixes the **Model**; the user picks per Agent.

**Functional Requirements:**

### FR-1: Create and persist a Specialist Agent

A **User** with builder role can create a new **Specialist Agent** by naming it, assigning it to a **Department**, and writing a system prompt. The Agent is persisted as a **Tenant**-scoped record with `created_at`, `owner_id`, and version metadata. Realizes UJ-1.

**Consequences (testable):**
- POST `/agents` with `{name, department_id, system_prompt}` returns `201` and the new agent's `id`.
- A GET `/agents/{id}` returns the same record.
- The Agent record is unreadable from a different **Tenant** (404, not 403 — no cross-tenant leak).

**Out of Scope:** Agent templates / marketplace — see §5.

### FR-2: Per-Agent Knowledge Base (upload + RAG retrieval)

A **User** can upload documents (PDF, TXT, Markdown, DOCX) to an **Agent**'s **Knowledge Base**. The platform chunks, embeds, indexes, and serves retrieval results back to the Agent at run time. KB access is **isolated to the Agent's Department** — an Agent in Credit cannot read KB documents of an Agent in HR.

**Consequences (testable):**
- Upload completes within 30 s per document up to 20 MB `[ASSUMPTION: doc-size ceiling]`.
- Retrieval at run time returns cited passages with document name and chunk reference.
- A direct read attempt by an HR-department Agent against a Credit-department KB returns an empty result set, never the Credit documents.

**Out of Scope:** Cross-Department KB sharing; KB versioning/diff; KB fine-tuning.

### FR-3: Per-Agent Tool configuration

A **User** can register a **Tool** on an **Agent** by providing: display name, header (including auth), input schema (JSON Schema), output schema (JSON Schema), and optional embedded Python for tighter control. Tools are invocable by the Agent during a **Workflow Run**.

**Consequences (testable):**
- A Tool registered with `{input_schema, output_schema}` validates every Agent-invoked call against the input schema; mismatched calls return a structured error to the Orchestrator.
- A Tool with embedded Python executes in a sandbox with no network egress `[ASSUMPTION: sandbox tech chosen by Architecture — see Open Questions]` and a 10-second execution budget `[ASSUMPTION: ceiling]`.
- Output that fails the output schema is rejected and logged in the **Audit Trail**.

**Out of Scope:** Tool marketplace; cross-Agent Tool sharing without explicit registration; Tool chaining inside a single call.

### FR-4: Per-Agent API Integration configuration

A **User** can register an **API Integration** on an **Agent** (e.g., a stubbed Gmail endpoint, a stubbed Calendar endpoint, a stubbed bank-core endpoint). The Integration is a named, reusable connection referenced by **Tools**.

**Consequences (testable):**
- An API Integration registered with `{base_url, auth_header, schema}` is callable from any Tool on that Agent.
- For the **MVP**, live OAuth to external systems is **out of scope** — Integrations point at stubbed FastAPI endpoints owned by the demo. See §5.

**Out of Scope:** OAuth flow; token refresh; rate-limit-aware clients; live third-party connectivity in MVP.

### FR-5: Per-Agent Model selection (user-configurable)

A **User** can pick the **Model** for an **Agent** at configuration time, choosing from the **Model Layer**'s configured providers (e.g., Anthropic Claude, OpenAI GPT, Google Gemini, local Ollama). The platform **does not fix any Model** — this is a user decision per Agent, every time.

**Consequences (testable):**
- The Agent Builder UI exposes a Model picker populated from the Model Layer's runtime-configured providers.
- Changing an Agent's Model does not require code changes — only a config update.
- A missing-provider error surfaces at run time, not at config time, with a clear message in the **Audit Trail**.

**Out of Scope:** A/B testing Models on the same Agent; automatic Model routing by query type; cost/latency optimization logic.

### FR-6: Agent ownership and Department scoping

Every **Agent** carries `tenant_id`, `department_id`, and `owner_id`. Only Users in the same **Tenant** can see the Agent; only Users in the same **Department** (or with builder role) can edit it.

**Consequences (testable):**
- Listing Agents returns only Agents in the caller's Tenant.
- Editing an Agent requires either `owner_id == caller` or builder role in the same Department.

**Feature-specific NFRs:**
- Security: Department isolation enforced at the data layer (row-level checks), not just at the API layer.

**Notes:** `[NOTE FOR PM]` Full RBAC beyond builder/manager/operator is a v2 concern — see §5.

## 4.2 Workflow Orchestrator

**Description:** The **Orchestrator** receives a natural-language or structured request, decomposes it into structured **Tasks** conforming to the **Task Schema**, dispatches Tasks to the right **Specialist Agents** over **MCP**, aggregates results, and **escalates to a human** on conflict or low confidence. MCP doubles as the shared **Task Store**. Realizes UJ-1 (steps 6–7), UJ-2 (steps 2–3).

**Functional Requirements:**

### FR-7: Workflow definition (natural-language or structured)

A **User** can create a **Workflow** by giving it a name and describing it in natural language ("pre-screen a business loan"), optionally with constraints ("must check credit policy, must check compliance, must verify document checklist"). The Workflow is persisted as a **Tenant**-scoped record.

**Consequences (testable):**
- POST `/workflows` with `{name, description}` returns `201` and the Workflow's `id`.
- The description is treated as a hint to the Orchestrator at run time — decomposition is dynamic per request, not hard-coded.

**Out of Scope:** A visual workflow editor (drag-drop nodes) for MVP — see §5. Workflows are described textually.

### FR-8: Dynamic task decomposition by the Orchestrator

On a **Workflow Run**, the **Orchestrator** (itself an LLM-driven coordinator) reads the request and produces a set of **Tasks**, each conforming to the **Task Schema** (`task / input / output / expected / criteria`). Each Task is routed to exactly one **Specialist Agent** based on the Agent's Department and declared capabilities.

**Consequences (testable):**
- Every emitted Task validates against the Task Schema; invalid Tasks are dropped and logged.
- Each Task names a target Agent by `id`; an unknown or wrong-Department target is rejected before dispatch.
- The decomposition is reproducible in the **Audit Trail**: the original request, the produced Tasks, and the routing rationale are all visible.

**Out of Scope:** Deterministic/non-LLM decomposition; ML-learned routing.

### FR-9: MCP-based task dispatch and aggregation

The platform dispatches each **Task** to its target **Agent** via **MCP**, collects the Agent's response (including any **Tool** invocations and **Knowledge Base** retrievals), and aggregates all responses into a single Workflow Run result. **MCP also serves as the shared Task Store** — Agents read their Tasks and write their results through MCP.

**Consequences (testable):**
- Every Task dispatch produces a structured MCP envelope; lost or malformed envelopes are retried up to 2 times with exponential backoff `[ASSUMPTION: retry policy]`.
- The Orchestrator waits for either all expected Agent responses or a timeout `[ASSUMPTION: timeout = 60 s per Agent]`, then aggregates.
- Aggregation logic is visible in the **Audit Trail** (which responses were merged, which were dropped).

**Out of Scope:** Streaming partial results during a Run for MVP (Run completes, then surfaces). `[NON-GOAL for MVP]`

### FR-10: Human-in-the-loop escalation

When the **Orchestrator** detects conflict between Agent responses, low confidence in an aggregation, or an explicit "needs human" flag from a Task, it pauses the **Workflow Run** and surfaces a human-review item with: current status, per-step feedback from each Agent, and a decision prompt. A **User** can resolve, override, or reject, and the Run resumes with the resolution recorded in the **Audit Trail**.

**Consequences (testable):**
- The Orchestrator emits an escalation event with `{run_id, conflicting_steps, suggested_resolutions}`.
- The User's resolution is recorded with `user_id`, `timestamp`, `rationale`, and the resumed Run inherits it.
- An unresolved escalation after `[ASSUMPTION: 5 minutes]` triggers a Run-level timeout visible in the Trace Dashboard.

**Out of Scope:** Multi approver workflows; out-of-band notification channels (email/Slack) in MVP.

### FR-11: Per-step feedback incorporation

A **Specialist Agent** can attach structured feedback to its response ("I am 60% confident", "this requires Operations to validate the document checklist"). The **Orchestrator** consumes this feedback when deciding to aggregate, escalate, or request a follow-up Task from another Agent.

**Consequences (testable):**
- Feedback is structured (confidence: 0–1, flags: enum, rationale: text), not free-form.
- The Orchestrator's consumption of feedback (whether it aggregated or escalated because of it) is logged in the Audit Trail.

## 4.3 Mini-App Builder

**Description:** From a description + expected output, an **Agent** (or the Orchestrator on behalf of one) generates a **Mini-App**: UI + auto-provisioned **JSONB Namespace** + auto-generated CRUD endpoints + a **Visibility Tier** + an **App Event** feed back into the **Action Bus**. Realizes UJ-1 (Climax), UJ-2 (step 4).

**Functional Requirements:**

### FR-12: Agent-emitted entity schema + UI spec

A **Specialist Agent** (or the Orchestrator) emits a JSON entity schema (`{fields, types, validations}`) plus a UI spec (`{layout, components, primary_actions}`) describing the Mini-App to be provisioned. The emission is triggered by the Orchestrator at the appropriate point in a Workflow Run.

**Consequences (testable):**
- The emitted schema validates against the platform's schema-meta-schema; invalid emissions are rejected and logged.
- The emission is captured in the **Audit Trail** with the originating Agent and prompt.

### FR-13: Auto-provisioned JSONB Namespace

On receipt of a valid entity schema, the platform provisions a **JSONB Namespace** for the Mini-App: rows carry `tenant_id`, `department_id`, `owner_id`, `visibility_tier`, plus the schema-defined fields stored as JSONB.

**Consequences (testable):**
- A new Mini-App gets a unique `app_id` and a writeable namespace within 2 s of emission.
- Every row written to the namespace carries the four access fields; none can be null.
- Per-tenant data isolation is enforced at the data layer.

**Out of Scope:** Per-Mini-App migrations; cross-Mini-App joins; per-row encryption at rest for MVP.

### FR-14: Auto-generated CRUD endpoints

Each Mini-App gets a set of CRUD endpoints (`POST/GET/LIST/PATCH/DELETE`) generated automatically from its entity schema, with **Visibility Tier** enforced.

**Consequences (testable):**
- The endpoints exist within 2 s of namespace provisioning.
- A `Private` Mini-App rejects reads from non-whitelisted Users with 403.
- A `Need-Auth` Mini-App rejects reads from Users outside the Department with 403.
- A `Public` Mini-App allows reads from any User in the same Tenant.

### FR-15: Auto-generated auth-gated UI

Each Mini-App gets a React UI rendered from its UI spec, served at a unique path, gated by the same **Visibility Tier** rules.

**Consequences (testable):**
- The UI is reachable within 5 s of endpoint generation.
- The UI enforces the same access rules as the CRUD endpoints (no client-only gating).
- Row edits, creates, and deletes are reflected in the **JSONB Namespace**.

### FR-16: Visibility Tier enforcement

The platform enforces **Visibility Tier** (`Public` / `Need-Auth` / `Private`) on every read and write to a Mini-App, at both the API and UI layers.

**Consequences (testable):**
- An anonymous request to a `Need-Auth` Mini-App returns 401.
- A same-Tenant, wrong-Department request to a `Need-Auth` Mini-App returns 403.
- A non-whitelisted same-Department request to a `Private` Mini-App returns 403.

### FR-17: App Event emission back into the Action Bus

Every material change to a Mini-App row (create, update, delete) emits a structured **App Event** onto the **Action Bus**, with `app_id`, `tenant_id`, `department_id`, `actor_user_id`, `event_type`, `payload`, `timestamp`.

**Consequences (testable):**
- App Events appear in the Action Bus within 1 s of the row change.
- App Events are visible in the **Audit Trail** of any Workflow Run subscribed to that event via an **Event Trigger** (FR-21).
- A lost event is detectable through a sequence-number gap visible in the Trace Dashboard.

## 4.4 Actions

**Description:** **Actions** fire **Agents** and **Workflows** on schedule or on event. Two kinds: **Schedule Trigger** (cron) and **Event Trigger** (fires on **App Event** or platform event).

**Functional Requirements:**

### FR-18: Schedule Trigger (cron)

A **User** can register a **Schedule Trigger** that fires a **Workflow Run** on a cron schedule (e.g., "every weekday at 09:00", "every Monday at 06:00").

**Consequences (testable):**
- The cron expression follows standard 5-field syntax.
- A Schedule Trigger fires within 60 s of its scheduled time `[ASSUMPTION: scheduler resolution]`.
- Each firing creates a Workflow Run visible in the Trace Dashboard.

### FR-19: Event Trigger (on App Event)

A **User** can register an **Event Trigger** that fires a **Workflow Run** when a matching **App Event** lands on the **Action Bus** (e.g., "when a Loan Case Mini-App creates a row, run the Post-Filing Workflow").

**Consequences (testable):**
- The Trigger declares a filter (`app_id`, `event_type`, optional JSON-path predicate on payload).
- Matching events fire a Workflow Run within 5 s.
- Non-matching events do not fire a Run.

### FR-20: Action Bus reliability

The **Action Bus** guarantees at-least-once delivery of App Events and Schedule Triggers to subscribers, with sequence numbers per `app_id` for gap detection.

**Consequences (testable):**
- A subscriber that crashes and restarts does not lose events — it resumes from the last-acked sequence.
- Sequence-number gaps are surfaced in the Trace Dashboard.

**Out of Scope:** Exactly-once semantics; cross-Tenant event fanout; event replay UI for MVP.

## 4.5 Audit, Trace & Decision Provenance

**Description:** Every decision in a **Workflow Run** is captured as an append-only **Audit Trail** entry and rendered in the **Trace Dashboard**. This satisfies the rubric's fourth bar and the banking-audit obligation. **This feature is not optional for MVP — it is load-bearing.**

**Functional Requirements:**

### FR-21: Per-step Audit Trail logging

Every step of a **Workflow Run** — Orchestrator decomposition, Task dispatch, Agent retrieval, Tool call, Model invocation (with Model name, prompt, latency), aggregation, escalation, Mini-App schema emission — is logged as an append-only **Audit Trail** entry.

**Consequences (testable):**
- Every entry carries `{run_id, step_id, agent_id, timestamp, type, input, output, latency_ms, model}`.
- Entries are append-only; no UPDATE or DELETE is permitted at any layer.
- An incomplete Run (crash, timeout) still has all entries logged up to the point of failure.

### FR-22: Trace Dashboard — timeline view

The **Trace Dashboard** renders an **Audit Trail** as a vertical timeline: each step is a card with type, agent, latency, and a "expand for detail" affordance.

**Consequences (testable):**
- A Run with 20+ steps renders in under 1 s on the demo laptop `[ASSUMPTION: demo hardware]`.
- Each card expands to show input, output, and the raw Audit Trail entry.
- The timeline is shareable by URL within the Tenant.

### FR-23: Trace Dashboard — collaboration graph

The **Trace Dashboard** renders the same **Audit Trail** as a collaboration graph: Orchestrator node at the top, Specialist Agent nodes below, edges labelled with Task type and status.

**Consequences (testable):**
- The graph renders in under 1 s for any Run with ≤ 10 Specialist Agent invocations `[ASSUMPTION: graph-size ceiling]`.
- Clicking a node opens the corresponding Audit Trail entries.
- The graph and the timeline are alternate views of the same underlying Audit Trail.

### FR-24: Audit export

A **User** can export a Run's **Audit Trail** as JSON (machine-readable) for downstream audit review.

**Consequences (testable):**
- The export contains every entry, signed with the Tenant's audit key `[ASSUMPTION: signing key management deferred to Architecture]`.
- The export is complete within 5 s for any Run with ≤ 1,000 entries.

## 4.6 Platform Foundation

**Description:** Cross-cutting platform capabilities that every feature above depends on: multi-tenancy, the Model Layer, the frontend, and operational health.

**Functional Requirements:**

### FR-25: Multi-Tenant data isolation

Every persisted record in VAIC carries a `tenant_id`. The data layer enforces isolation: no query may return rows from another Tenant, even under direct DB access by a misconfigured feature.

**Consequences (testable):**
- ATenantA User's request never returns TenantB rows at any endpoint.
- Direct SQL inspection confirms row-level filtering by `tenant_id` on every table.

### FR-26: Model Layer (provider-agnostic)

The **Model Layer** abstracts LLM providers (Anthropic, OpenAI, Google, local) behind a single interface. **Agents** specify their **Model** by `{provider, model_name, parameters}`; the Model Layer routes the call.

**Consequences (testable):**
- Adding a new provider does not require changes to Agent, Orchestrator, or Mini-App Builder code.
- A provider outage for one Model does not crash Agents configured with other Models.

### FR-27: ReactJS frontend SPA

The platform exposes a ReactJS single-page application covering: Agent Builder, Workflow Orchestrator (definition + Run view), Mini-App catalog (list + open), Trace Dashboard, Action configuration, and minimal account/Department switching.

**Consequences (testable):**
- The SPA is the only UI surface in MVP; no mobile app (see §5).
- Design direction follows `docs/UI Screenshot.png` referenced in the brief.

### FR-28: Tenant bootstrapping (demo-ready)

For the hackathon, a script or admin command bootstraps a **Tenant** with: at least one User per role, at least two **Departments**, and at least one pre-configured **Workflow** ready to Run. This is for demo repeatability — **the platform itself remains flow-agnostic**.

**Consequences (testable):**
- Running the bootstrap produces a runnable Tenant in under 60 s.
- The bootstrap is idempotent — running it twice does not corrupt data.
- The bootstrap is NOT a hard-coded demo: the same platform surfaces used to build the pre-configured Workflow are available to the User at run time.
