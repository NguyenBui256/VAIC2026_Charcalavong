---
title: VAIC — Enterprise AI-Agent Platform for Banking Automation
status: final
created: 2026-07-17
updated: 2026-07-17
finalized: 2026-07-17
source_brief: _bmad-output/planning-artifacts/briefs/brief-VAIC-2026-07-17/brief.md
hackathon: Hack CX Together 2026 (SHB — Saigon-Hai Bank)
entry_point: Vision + Features (capability-first)
---


# PRD: VAIC — Enterprise AI-Agent Platform for Banking Automation


> Working title — confirm.


## 0. Document Purpose


This PRD specifies **VAIC**, a multi-tenant enterprise AI-agent platform that lets a bank configure specialist AI agents, coordinate them through a workflow orchestrator, generate working mini-apps with auto-provisioned backends, and trigger runs on schedule or event. It is written for: (a) the **product manager** (Nguyen) and **mentor** reviewing scope and rubric alignment; (b) the **build team** who need crisp feature-level requirements with stable IDs; (c) **downstream BMad workflows** — UX, Architecture, Epics & Stories — which consume FRs and UJs verbatim.


The PRD is **platform-capability-first**, not scenario-first: it specifies what the platform must be able to do. A demo at the close of the 2-day build is one configured instance of the platform, not its scope.


The document is structured as: Vision → Target User → Glossary → Features (the platform's six capability groups) → Non-Goals → MVP Scope (demo-scoped platform) → Success Metrics (mapped to the SHB rubric) → Constraints, Guardrails & NFRs → Integration & Dependencies → Risks → Stakeholders → Open Questions → Assumptions Index. Domain nouns are defined once in the Glossary and used verbatim everywhere else. Inferences are tagged inline `[ASSUMPTION: ...]` and indexed in §13. Deferred items are tagged `[NON-GOAL for MVP]` inline.


Source intake: the product brief v2 (`_bmad-output/planning-artifacts/briefs/brief-VAIC-2026-07-17/brief.md`) and the SHB Hack CX Together 2026 problem statement (verbatim, see §8.3). The brief's tech-stack choices (FastAPI, PostgreSQL with JSONB, ReactJS, MCP) are treated as **technical constraints** the team has decided, not feature-level requirements.


## 1. Vision


Vietnamese bank employees and managers spend their day moving **cross-department, multi-step flows** — lending, KYC/AML, exception handling, approvals — across email, chat, Excel, and tribal knowledge. Single-agent chatbots help with *a question* but not *a process*: they cannot hold state across departments, hand off cleanly, or produce anything persistent. The gap is the **flow**, not the answer.


**VAIC closes that gap.** It is a web platform where a bank's own staff can configure multiple **Specialist Agents** (each with its own knowledge base, tools, API integrations, prompt, and model), coordinate them through a **Workflow Orchestrator** that decomposes a complex request into structured tasks, dispatch those tasks over **MCP**, and have the agents **generate Mini-Apps** — each with an auto-provisioned backend and per-tenant storage — that emit events back into the orchestrator. The work now lives somewhere: a chat becomes a system that carries the work.


The closed loop — **agent generates app → app emits events → agents react** — is what makes VAIC architecturally novel in a 2026 category where agent builders, RAG, and MCP are commodity. The competitive wedge is not any single feature; it is the **integration of those features aimed at one vertical** (Vietnamese banking cross-department work) plus **execution speed**.


For the **Hack CX Together 2026** demo, the platform must demonstrably run end-to-end on one configured cross-department flow, satisfying the rubric's four bars (specialist collaboration, planner decomposition, real tool use, trace dashboard) plus the brief's stretch (a generated mini-app with real storage).


## 2. Target User


### 2.1 Jobs To Be Done


**Primary users — bank employees and managers running cross-department work daily:**
- "Help me move this loan application through Credit, Legal, and Operations without me chasing each desk."
- "Help me capture the decision trail on this exception so audit can reconstruct it next quarter."
- "Help me turn a flow my team runs on Excel every week into a small app my team actually operates — without filing an IT ticket."


**Secondary users — IT / internal-tools teams:**
- "Help me give the business a way to ship its own automation without my team being the bottleneck."


**Builder (hackathon context):**
- "Help me prove at demo time that the platform is real — that any flow can be configured and run, not a hard-coded demo."


### 2.2 Non-Users (v1)


- **End customers of the bank** — retail and corporate customers are *not* direct VAIC users in v1. They may be the *subject* of a workflow (e.g., a loan applicant) but never the operator.
- **External developers / third-party integrators** — VAIC is configured by the bank's own staff and IT, not exposed as a public platform-as-a-service in v1. `[NON-GOAL for MVP]`
- **Regulators / auditors as direct users** — they consume **Audit Trails** produced by VAIC, but do not operate VAIC directly in v1.


### 2.3 Key User Journeys


VAIC is an enterprise/dev platform; the journeys are operator journeys, not consumer ones. Two journeys carry the demo.


- **UJ-1. Linh configures a specialist agent and a workflow end-to-end.**
  - **Persona + context:** Linh, an internal-tools lead at a Vietnamese bank, has been asked by the Credit department to automate the pre-screening leg of business-loan applications.
  - **Entry state:** Authenticated into VAIC on desktop web. She has PDFs of the bank's lending policy and SHB-relevant NHNN circular excerpts ready.
  - **Path:**
    1. Opens **Agent Builder**, creates a new **Specialist Agent** named "Credit Analyst", assigns it to the Credit department.
    2. Uploads the policy PDFs into the agent's **Knowledge Base**.
    3. Configures two **Tools** for the agent: a financial-ratio calculator (input schema: financial summary JSON; output schema: ratio results + verdict) and a policy-lookup retriever (input: query string; output: cited passages).
    4. Picks a **Model** for the agent (provider + model, chosen from the platform's model layer — `[ASSUMPTION: at least one provider available at demo]`).
    5. Repeats steps 1–4 for "Compliance Analyst" (KB: AML/KYC circulars; Tool: sanctions-list check) and "Operations Analyst" (KB: ops SOPs; Tool: document checklist verifier).
    6. Opens **Workflow Orchestrator**, describes the flow in natural language ("pre-screen a business loan: pull financials, check policy compliance, verify document checklist, return a consolidated decision"), saves it.
    7. Clicks **Run** on a test loan case.
  - **Climax:** The **Trace Dashboard** shows the **Orchestrator** decompose the request into structured tasks, dispatch each to the right **Specialist Agent** over **MCP**, and aggregate the results. The dashboard renders the collaboration timeline and the per-step **Audit Trail**.
  - **Resolution:** Linh sees a consolidated decision plus a generated **Mini-App** ("Business Loan Pre-Screen Case") with real persisted data, and can replay the trace for audit.


- **UJ-2. A hackathon judge watches one configured flow prove the platform.**
  - **Persona + context:** A judge at Hack CX Together 2026, walks to the VAIC demo station with the rubric in hand.
  - **Entry state:** VAIC is running on the demo laptop, pre-configured with one cross-department flow.
  - **Path:**
    1. Hears the team describe the flow in one sentence.
    2. Watches a request submitted to the **Workflow Orchestrator**.
    3. Watches the **Trace Dashboard** populate live: planner decomposition → specialist dispatch → tool invocations → aggregation → human-escalation (if triggered).
    4. Opens the generated **Mini-App** with its own URL, edits a row, watches the edit **emit an event** back into the orchestrator.
  - **Climax:** The judge sees all four rubric bars clear in one screen: specialist collaboration, planner decomposition, real tool use, and the trace — plus the stretch artifact (a generated mini-app with real storage).
  - **Resolution:** The judge walks away with one mental model: "agents that plan, use tools, and ship an app — not a chatbot." `[ASSUMPTION: judge availability and format]`


*Scope dial: heavier — both UJs feed downstream UX (the operator's configuration surfaces and the runtime Trace Dashboard) and architecture (orchestration, MCP task store, JSONB-backed Mini-App provisioning). Edge cases per feature are captured inside §4.*


## 3. Glossary


*Downstream workflows and readers must use these terms exactly. FRs, UJs, and SMs use Glossary terms verbatim; introducing a synonym anywhere in the PRD is a discipline violation.*


- **Tenant** — An enterprise (a bank). Owns users, departments, agents, workflows, mini-apps, and audit trails. All data is tenant-scoped; cross-tenant reads are forbidden. Cardinality: one Tenant has many Users, Departments, Specialist Agents, Workflows, Mini-Apps.
- **Department** — An organizational unit within a Tenant (e.g., Credit, Legal/Compliance, Operations). Scopes Specialist Agent ownership, Knowledge Base visibility, and Mini-App access.
- **User** — A person operating VAIC within a Tenant. Has at least one role (e.g., manager, operator, builder). `[ASSUMPTION: v1 roles are light — builder + manager + operator; full RBAC engine deferred.]`
- **Specialist Agent** (or **Agent**) — A Tenant-scoped configuration consisting of: a **Knowledge Base** reference, a system prompt, a **Model** selection, a set of **Tools**, optional **API Integrations**, and a owning **Department**. Executes tasks emitted by the **Workflow Orchestrator**. Distinct from the **Orchestrator**.
- **Orchestrator** (or **Planner**) — A coordinator agent that receives a complex request, decomposes it into structured **Tasks** per the **Task Schema**, dispatches Tasks to **Specialist Agents** via **MCP**, aggregates results, and **escalates to a human** on conflict or low confidence.
- **Knowledge Base** (or **KB**) — A per-Agent corpus of uploaded documents (policy PDFs, regulations, SOPs, text) retrieved via RAG. Isolated to the Agent's **Department** — Credit KB is unreadable by HR Agent.
- **Tool** — A callable capability owned by an **Agent**. Defined by: header (incl. auth), input schema, output schema, optional embedded Python for tighter control. Examples: financial-ratio calculator, sanctions-list check, policy retriever.
- **API Integration** — A reusable external-system connector (e.g., Gmail, Calendar, internal bank core) configured per Agent. `[NON-GOAL for MVP: live OAuth to external systems — see §5.]`
- **Model** — The LLM provider + model an Agent uses. **Selected per Agent at configuration time by the user — never fixed by the platform.** Examples: Claude Sonnet, Claude Haiku, GPT-4o, Gemini 2.5. The platform's **Model Layer** is provider-agnostic.
- **MCP** — Model Context Protocol. Used both as the agent↔tool/task transport and as the shared **Task Store** that Specialist Agents read from and write to during a **Workflow Run**.
- **Task** — A unit of work produced by the **Orchestrator** decomposition, conforming to the **Task Schema** (`task / input / output / expected / criteria`). Dispatched to one Specialist Agent.
- **Task Schema** — The JSON/YAML contract every Task conforms to. Full structure in `addendum.md` §A1.
- **Workflow** — A configurable cross-department flow describable in natural language, executed by the **Orchestrator**. A Workflow is a template; a **Workflow Run** is one execution.
- **Workflow Run** (or **Run**) — One end-to-end execution of a **Workflow**: the original request, every Task emitted, every Specialist Agent response, every Tool call, every aggregation, and any human-escalation. The unit of **Audit Trail**.
- **Mini-App** — A working application generated by an Agent (or agent team) from a description + expected output. Composed of: a UI, an auto-provisioned **JSONB Namespace**, auto-generated CRUD endpoints, a **Visibility Tier**, and a feed of **App Events** back into the **Action Bus**.
- **JSONB Namespace** — A per-Mini-App logical data namespace backed by PostgreSQL JSONB columns. Carries `tenant_id`, `department_id`, `owner_id`, and Visibility Tier on every row. Flexible per-app schema without per-app migrations.
- **Visibility Tier** — One of `Public` / `Need-Auth` (account + department) / `Private` (whitelisted). Enforced on Mini-App access.
- **App Event** — A structured signal emitted by a **Mini-App** into the **Action Bus** (e.g., "row created", "form submitted", "field edited"). Triggers **Actions** or new **Workflow Runs**.
- **Action** — A platform-level trigger that fires a **Specialist Agent** or **Workflow Run**. Two kinds: **Schedule Trigger** (cron) and **Event Trigger** (fires on App Event or platform event).
- **Action Bus** — The internal event queue that routes App Events, Schedule Triggers, and platform signals to subscribed Agents and Workflows.
- **Audit Trail** (or **Trace**) — The append-only record of every decision in a Workflow Run: docs retrieved, Tools called, prompts sent, Model used, latency per step, aggregation logic, and any human-escalation. The unit of regulatory and rubric accountability.
- **Trace Dashboard** — The UX surface that renders an **Audit Trail** as timeline + collaboration graph + per-step detail. The primary judge-facing surface.
- **Model Layer** — The platform-agnostic abstraction over LLM providers. Lets each Agent select its **Model** without coupling the rest of the platform to a single vendor.


## 4. Features


The platform's capability surface is organized into six feature groups. **FRs are numbered globally (FR-1 through FR-32) for stable downstream references.** Each FR lists testable consequences; feature-specific NFRs and open questions live inline.


### 4.1 Agent Builder


**Description:** Lets a user configure a **Specialist Agent** end-to-end — identity, **Knowledge Base**, **Tools**, **API Integrations**, prompt, and **Model** — and persist it as a **Tenant**-scoped record. Realizes UJ-1 (steps 1–5). Per-Agent **KB** isolation enforces department-scoped access. The platform never fixes the **Model**; the user picks per Agent.


**Functional Requirements:**


#### FR-1: Create and persist a Specialist Agent


A **User** with builder role can create a new **Specialist Agent** by naming it, assigning it to a **Department**, and writing a system prompt. The Agent is persisted as a **Tenant**-scoped record with `created_at`, `owner_id`, and version metadata. Realizes UJ-1.


**Consequences (testable):**
- POST `/agents` with `{name, department_id, system_prompt}` returns `201` and the new agent's `id`.
- A GET `/agents/{id}` returns the same record.
- The Agent record is unreadable from a different **Tenant** (404, not 403 — no cross-tenant leak).


**Out of Scope:** Agent templates / marketplace — see §5.


#### FR-2: Per-Agent Knowledge Base (upload + RAG retrieval)


A **User** can upload documents (PDF, TXT, Markdown, DOCX) to an **Agent**'s **Knowledge Base**. The platform chunks, embeds, indexes, and serves retrieval results back to the Agent at run time. KB access is **isolated to the Agent's Department** — an Agent in Credit cannot read KB documents of an Agent in HR.


**Consequences (testable):**
- Upload completes within 30 s per document up to 20 MB `[ASSUMPTION: doc-size ceiling]`.
- Retrieval at run time returns cited passages with document name and chunk reference.
- A direct read attempt by an HR-department Agent against a Credit-department KB returns an empty result set, never the Credit documents.


**Out of Scope:** Cross-Department KB sharing; KB versioning/diff; KB fine-tuning.


#### FR-3: Per-Agent Tool configuration


A **User** can register a **Tool** on an **Agent** by providing: display name, header (including auth), input schema (JSON Schema), output schema (JSON Schema), and optional embedded Python for tighter control. Tools are invocable by the Agent during a **Workflow Run**.


**Consequences (testable):**
- A Tool registered with `{input_schema, output_schema}` validates every Agent-invoked call against the input schema; mismatched calls return a structured error to the Orchestrator.
- A Tool with embedded Python executes in a sandbox with no network egress `[ASSUMPTION: sandbox tech chosen by Architecture — see Open Questions]` and a 10-second execution budget `[ASSUMPTION: ceiling]`.
- Output that fails the output schema is rejected and logged in the **Audit Trail**.


**Out of Scope:** Tool marketplace; cross-Agent Tool sharing without explicit registration; Tool chaining inside a single call.


#### FR-4: Per-Agent API Integration configuration


A **User** can register an **API Integration** on an **Agent** (e.g., a stubbed Gmail endpoint, a stubbed Calendar endpoint, a stubbed bank-core endpoint). The Integration is a named, reusable connection referenced by **Tools**.


**Consequences (testable):**
- An API Integration registered with `{base_url, auth_header, schema}` is callable from any Tool on that Agent.
- For the **MVP**, live OAuth to external systems is **out of scope** — Integrations point at stubbed FastAPI endpoints owned by the demo. See §5.


**Out of Scope:** OAuth flow; token refresh; rate-limit-aware clients; live third-party connectivity in MVP.


#### FR-5: Per-Agent Model selection (user-configurable)


A **User** can pick the **Model** for an **Agent** at configuration time, choosing from the **Model Layer**'s configured providers (e.g., Anthropic Claude, OpenAI GPT, Google Gemini, local Ollama). The platform **does not fix any Model** — this is a user decision per Agent, every time.


**Consequences (testable):**
- The Agent Builder UI exposes a Model picker populated from the Model Layer's runtime-configured providers.
- Changing an Agent's Model does not require code changes — only a config update.
- A missing-provider error surfaces at run time, not at config time, with a clear message in the **Audit Trail**.


**Out of Scope:** A/B testing Models on the same Agent; automatic Model routing by query type; cost/latency optimization logic.


#### FR-6: Agent ownership and Department scoping


Every **Agent** carries `tenant_id`, `department_id`, and `owner_id`. Only Users in the same **Tenant** can see the Agent; only Users in the same **Department** (or with builder role) can edit it.


**Consequences (testable):**
- Listing Agents returns only Agents in the caller's Tenant.
- Editing an Agent requires either `owner_id == caller` or builder role in the same Department.


**Feature-specific NFRs:**
- Security: Department isolation enforced at the data layer (row-level checks), not just at the API layer.


**Notes:** `[NOTE FOR PM]` Full RBAC beyond builder/manager/operator is a v2 concern — see §5.


### 4.2 Workflow Orchestrator


**Description:** The **Orchestrator** receives a natural-language or structured request, decomposes it into structured **Tasks** conforming to the **Task Schema**, dispatches Tasks to the right **Specialist Agents** over **MCP**, aggregates results, and **escalates to a human** on conflict or low confidence. MCP doubles as the shared **Task Store**. Realizes UJ-1 (steps 6–7), UJ-2 (steps 2–3).


**Functional Requirements:**


#### FR-7: Workflow definition (natural-language or structured)


A **User** can create a **Workflow** by giving it a name and describing it in natural language ("pre-screen a business loan"), optionally with constraints ("must check credit policy, must check compliance, must verify document checklist"). The Workflow is persisted as a **Tenant**-scoped record.


**Consequences (testable):**
- POST `/workflows` with `{name, description}` returns `201` and the Workflow's `id`.
- The description is treated as a hint to the Orchestrator at run time — decomposition is dynamic per request, not hard-coded.


**Out of Scope:** A visual workflow editor (drag-drop nodes) for MVP — see §5. Workflows are described textually.


#### FR-8: Dynamic task decomposition by the Orchestrator


On a **Workflow Run**, the **Orchestrator** (itself an LLM-driven coordinator) reads the request and produces a set of **Tasks**, each conforming to the **Task Schema** (`task / input / output / expected / criteria`). Each Task is routed to exactly one **Specialist Agent** based on the Agent's Department and declared capabilities.


**Consequences (testable):**
- Every emitted Task validates against the Task Schema; invalid Tasks are dropped and logged.
- Each Task names a target Agent by `id`; an unknown or wrong-Department target is rejected before dispatch.
- The decomposition is reproducible in the **Audit Trail**: the original request, the produced Tasks, and the routing rationale are all visible.


**Out of Scope:** Deterministic/non-LLM decomposition; ML-learned routing.


#### FR-9: MCP-based task dispatch and aggregation


The platform dispatches each **Task** to its target **Agent** via **MCP**, collects the Agent's response (including any **Tool** invocations and **Knowledge Base** retrievals), and aggregates all responses into a single Workflow Run result. **MCP also serves as the shared Task Store** — Agents read their Tasks and write their results through MCP.


**Consequences (testable):**
- Every Task dispatch produces a structured MCP envelope; lost or malformed envelopes are retried up to 2 times with exponential backoff `[ASSUMPTION: retry policy]`.
- The Orchestrator waits for either all expected Agent responses or a timeout `[ASSUMPTION: timeout = 60 s per Agent]`, then aggregates.
- Aggregation logic is visible in the **Audit Trail** (which responses were merged, which were dropped).


**Out of Scope:** Streaming partial results during a Run for MVP (Run completes, then surfaces). `[NON-GOAL for MVP]`


#### FR-10: Human-in-the-loop escalation


When the **Orchestrator** detects conflict between Agent responses, low confidence in an aggregation, or an explicit "needs human" flag from a Task, it pauses the **Workflow Run** and surfaces a human-review item with: current status, per-step feedback from each Agent, and a decision prompt. A **User** can resolve, override, or reject, and the Run resumes with the resolution recorded in the **Audit Trail**.


**Consequences (testable):**
- The Orchestrator emits an escalation event with `{run_id, conflicting_steps, suggested_resolutions}`.
- The User's resolution is recorded with `user_id`, `timestamp`, `rationale`, and the resumed Run inherits it.
- An unresolved escalation after `[ASSUMPTION: 5 minutes]` triggers a Run-level timeout visible in the Trace Dashboard.


**Out of Scope:** Multi approver workflows; out-of-band notification channels (email/Slack) in MVP.


#### FR-11: Per-step feedback incorporation


A **Specialist Agent** can attach structured feedback to its response ("I am 60% confident", "this requires Operations to validate the document checklist"). The **Orchestrator** consumes this feedback when deciding to aggregate, escalate, or request a follow-up Task from another Agent.


**Consequences (testable):**
- Feedback is structured (confidence: 0–1, flags: enum, rationale: text), not free-form.
- The Orchestrator's consumption of feedback (whether it aggregated or escalated because of it) is logged in the Audit Trail.


### 4.3 Mini-App Builder


**Description:** From a description + expected output, an **Agent** (or the Orchestrator on behalf of one) generates a **Mini-App**: UI + auto-provisioned **JSONB Namespace** + auto-generated CRUD endpoints + a **Visibility Tier** + an **App Event** feed back into the **Action Bus**. Realizes UJ-1 (Climax), UJ-2 (step 4).


**Functional Requirements:**


#### FR-12: Agent-emitted entity schema + UI spec


A **Specialist Agent** (or the Orchestrator) emits a JSON entity schema (`{fields, types, validations}`) plus a UI spec (`{layout, components, primary_actions}`) describing the Mini-App to be provisioned. The emission is triggered by the Orchestrator at the appropriate point in a Workflow Run.


**Consequences (testable):**
- The emitted schema validates against the platform's schema-meta-schema; invalid emissions are rejected and logged.
- The emission is captured in the **Audit Trail** with the originating Agent and prompt.


#### FR-13: Auto-provisioned JSONB Namespace


On receipt of a valid entity schema, the platform provisions a **JSONB Namespace** for the Mini-App: rows carry `tenant_id`, `department_id`, `owner_id`, `visibility_tier`, plus the schema-defined fields stored as JSONB.


**Consequences (testable):**
- A new Mini-App gets a unique `app_id` and a writeable namespace within 2 s of emission.
- Every row written to the namespace carries the four access fields; none can be null.
- Per-tenant data isolation is enforced at the data layer.


**Out of Scope:** Per-Mini-App migrations; cross-Mini-App joins; per-row encryption at rest for MVP.


#### FR-14: Auto-generated CRUD endpoints


Each Mini-App gets a set of CRUD endpoints (`POST/GET/LIST/PATCH/DELETE`) generated automatically from its entity schema, with **Visibility Tier** enforced.


**Consequences (testable):**
- The endpoints exist within 2 s of namespace provisioning.
- A `Private` Mini-App rejects reads from non-whitelisted Users with 403.
- A `Need-Auth` Mini-App rejects reads from Users outside the Department with 403.
- A `Public` Mini-App allows reads from any User in the same Tenant.


#### FR-15: Auto-generated auth-gated UI


Each Mini-App gets a React UI rendered from its UI spec, served at a unique path, gated by the same **Visibility Tier** rules.


**Consequences (testable):**
- The UI is reachable within 5 s of endpoint generation.
- The UI enforces the same access rules as the CRUD endpoints (no client-only gating).
- Row edits, creates, and deletes are reflected in the **JSONB Namespace**.


#### FR-16: Visibility Tier enforcement


The platform enforces **Visibility Tier** (`Public` / `Need-Auth` / `Private`) on every read and write to a Mini-App, at both the API and UI layers.


**Consequences (testable):**
- An anonymous request to a `Need-Auth` Mini-App returns 401.
- A same-Tenant, wrong-Department request to a `Need-Auth` Mini-App returns 403.
- A non-whitelisted same-Department request to a `Private` Mini-App returns 403.


#### FR-17: App Event emission back into the Action Bus


Every material change to a Mini-App row (create, update, delete) emits a structured **App Event** onto the **Action Bus**, with `app_id`, `tenant_id`, `department_id`, `actor_user_id`, `event_type`, `payload`, `timestamp`.


**Consequences (testable):**
- App Events appear in the Action Bus within 1 s of the row change.
- App Events are visible in the **Audit Trail** of any Workflow Run subscribed to that event via an **Event Trigger** (FR-21).
- A lost event is detectable through a sequence-number gap visible in the Trace Dashboard.


### 4.4 Actions


**Description:** **Actions** fire **Agents** and **Workflows** on schedule or on event. Two kinds: **Schedule Trigger** (cron) and **Event Trigger** (fires on **App Event** or platform event).


**Functional Requirements:**


#### FR-18: Schedule Trigger (cron)


A **User** can register a **Schedule Trigger** that fires a **Workflow Run** on a cron schedule (e.g., "every weekday at 09:00", "every Monday at 06:00").


**Consequences (testable):**
- The cron expression follows standard 5-field syntax.
- A Schedule Trigger fires within 60 s of its scheduled time `[ASSUMPTION: scheduler resolution]`.
- Each firing creates a Workflow Run visible in the Trace Dashboard.


#### FR-19: Event Trigger (on App Event)


A **User** can register an **Event Trigger** that fires a **Workflow Run** when a matching **App Event** lands on the **Action Bus** (e.g., "when a Loan Case Mini-App creates a row, run the Post-Filing Workflow").


**Consequences (testable):**
- The Trigger declares a filter (`app_id`, `event_type`, optional JSON-path predicate on payload).
- Matching events fire a Workflow Run within 5 s.
- Non-matching events do not fire a Run.


#### FR-20: Action Bus reliability


The **Action Bus** guarantees at-least-once delivery of App Events and Schedule Triggers to subscribers, with sequence numbers per `app_id` for gap detection.


**Consequences (testable):**
- A subscriber that crashes and restarts does not lose events — it resumes from the last-acked sequence.
- Sequence-number gaps are surfaced in the Trace Dashboard.


**Out of Scope:** Exactly-once semantics; cross-Tenant event fanout; event replay UI for MVP.


### 4.5 Audit, Trace & Decision Provenance


**Description:** Every decision in a **Workflow Run** is captured as an append-only **Audit Trail** entry and rendered in the **Trace Dashboard**. This satisfies the rubric's fourth bar and the banking-audit obligation. **This feature is not optional for MVP — it is load-bearing.**


**Functional Requirements:**


#### FR-21: Per-step Audit Trail logging


Every step of a **Workflow Run** — Orchestrator decomposition, Task dispatch, Agent retrieval, Tool call, Model invocation (with Model name, prompt, latency), aggregation, escalation, Mini-App schema emission — is logged as an append-only **Audit Trail** entry.


**Consequences (testable):**
- Every entry carries `{run_id, step_id, agent_id, timestamp, type, input, output, latency_ms, model}`.
- Entries are append-only; no UPDATE or DELETE is permitted at any layer.
- An incomplete Run (crash, timeout) still has all entries logged up to the point of failure.


#### FR-22: Trace Dashboard — timeline view


The **Trace Dashboard** renders an **Audit Trail** as a vertical timeline: each step is a card with type, agent, latency, and a "expand for detail" affordance.


**Consequences (testable):**
- A Run with 20+ steps renders in under 1 s on the demo laptop `[ASSUMPTION: demo hardware]`.
- Each card expands to show input, output, and the raw Audit Trail entry.
- The timeline is shareable by URL within the Tenant.


#### FR-23: Trace Dashboard — collaboration graph


The **Trace Dashboard** renders the same **Audit Trail** as a collaboration graph: Orchestrator node at the top, Specialist Agent nodes below, edges labelled with Task type and status.


**Consequences (testable):**
- The graph renders in under 1 s for any Run with ≤ 10 Specialist Agent invocations `[ASSUMPTION: graph-size ceiling]`.
- Clicking a node opens the corresponding Audit Trail entries.
- The graph and the timeline are alternate views of the same underlying Audit Trail.


#### FR-24: Audit export


A **User** can export a Run's **Audit Trail** as JSON (machine-readable) for downstream audit review.


**Consequences (testable):**
- The export contains every entry, signed with the Tenant's audit key `[ASSUMPTION: signing key management deferred to Architecture]`.
- The export is complete within 5 s for any Run with ≤ 1,000 entries.


### 4.6 Platform Foundation


**Description:** Cross-cutting platform capabilities that every feature above depends on: multi-tenancy, the Model Layer, the frontend, and operational health.


**Functional Requirements:**


#### FR-25: Multi-Tenant data isolation


Every persisted record in VAIC carries a `tenant_id`. The data layer enforces isolation: no query may return rows from another Tenant, even under direct DB access by a misconfigured feature.


**Consequences (testable):**
- ATenantA User's request never returns TenantB rows at any endpoint.
- Direct SQL inspection confirms row-level filtering by `tenant_id` on every table.


#### FR-26: Model Layer (provider-agnostic)


The **Model Layer** abstracts LLM providers (Anthropic, OpenAI, Google, local) behind a single interface. **Agents** specify their **Model** by `{provider, model_name, parameters}`; the Model Layer routes the call.


**Consequences (testable):**
- Adding a new provider does not require changes to Agent, Orchestrator, or Mini-App Builder code.
- A provider outage for one Model does not crash Agents configured with other Models.


#### FR-27: ReactJS frontend SPA


The platform exposes a ReactJS single-page application covering: Agent Builder, Workflow Orchestrator (definition + Run view), Mini-App catalog (list + open), Trace Dashboard, Action configuration, and minimal account/Department switching.


**Consequences (testable):**
- The SPA is the only UI surface in MVP; no mobile app (see §5).
- Design direction follows `docs/UI Screenshot.png` referenced in the brief.


#### FR-28: Tenant bootstrapping (demo-ready)


For the hackathon, a script or admin command bootstraps a **Tenant** with: at least one User per role, at least two **Departments**, and at least one pre-configured **Workflow** ready to Run. This is for demo repeatability — **the platform itself remains flow-agnostic**.


**Consequences (testable):**
- Running the bootstrap produces a runnable Tenant in under 60 s.
- The bootstrap is idempotent — running it twice does not corrupt data.
- The bootstrap is NOT a hard-coded demo: the same platform surfaces used to build the pre-configured Workflow are available to the User at run time.


## 5. Non-Goals (Explicit)


- **Mobile native apps.** v1 is web-only.
- **Cross-Tenant Mini-App marketplace / sharing.**
- **Fine-grained RBAC engine beyond Department + Visibility Tier + builder/manager/operator roles.**
- **Billing / commercial packaging.**
- **Agent-generated Mini-App code export to external repos.** Mini-Apps live inside VAIC.
- **Visual drag-drop workflow editor.** Workflows are described textually in v1; the Orchestrator decomposes dynamically.
- **Live OAuth to external systems** (Gmail, Calendar, bank core) in MVP. API Integrations point at stubbed FastAPI endpoints.
- **Streaming partial Agent responses** during a Run for MVP.
- **Exactly-once event delivery.** At-least-once with sequence numbers is the v1 contract.
- **Vietnamese-language enforcement on Agent outputs.** Agents respond in whatever language the prompt requests; the platform does not translate.
- **Public APIs / third-party developer surface.**
- **Production-grade secrets management.** Demo uses environment-loaded keys; rotation and HSM are post-hackathon.
- **Multi-region deployment.** Single-region for v1.


## 6. MVP Scope


### 6.1 In Scope (Demo-Scoped Platform)


All six feature groups (§4.1–§4.6) ship in working form for the demo:


- **Agent Builder** — full CRUD; at least 3 pre-configured Specialist Agents in the demo Tenant (suggested: Credit Analyst, Compliance Analyst, Operations Analyst — but the platform supports any configuration). `[ASSUMPTION: team will pre-configure at least 3 to satisfy rubric bar 1]`
- **Workflow Orchestrator** — full decomposition + MCP dispatch + aggregation + human escalation; at least 1 pre-configured Workflow in the demo Tenant.
- **Mini-App Builder** — auto-provisioning live; at least 1 Mini-App generated live during the demo Run.
- **Actions** — Schedule Trigger and Event Trigger both functional; at least 1 Event Trigger firing during the demo (Mini-App → Workflow).
- **Audit, Trace & Decision Provenance** — full Audit Trail logging; Trace Dashboard rendering both timeline and collaboration graph views.
- **Platform Foundation** — single-Tenant demo, multi-Department, Model Layer working with at least one provider, React SPA, Tenant bootstrap script.


### 6.2 Out of Scope for MVP (v2+)


- Everything in §5.
- **Vietnamese-language UI** beyond labels — agent output language is prompt-controlled, not platform-enforced.
- **Webhook ingress** — only internal App Events trigger Workflows for MVP.
- **Mini-App theming / branding controls.**
- **Audit Trail archival to cold storage.** Demo keeps the last 7 days. `[ASSUMPTION: retention window]`
- **Multi-Model routing per Agent** (one Model per Agent for MVP; routing across Models per query is v2).
- **Agent fine-tuning / training.**
- **Benchmark-vs-chatbot side-by-side** (brief marked this stretch; not scored by rubric — deferred).


## 7. Success Metrics


*Each SM cross-references the FR(s) it validates. Counter-metrics counterbalance specific primary metrics.*


**Primary (rubric-aligned)**


- **SM-1**: Specialist collaboration visible — at demo, the platform demonstrably runs 2–3 Specialist Agents in one Workflow Run, each with its own KB and Tools. Target: ≥ 2 Agents, recommended 3. Validates FR-1, FR-7, FR-8, FR-9. **(SHB rubric bar 1.)**
- **SM-2**: Planner decomposition visible — at demo, the Orchestrator visibly decomposes the request into ≥ 2 Tasks and routes each to the right Agent. Target: ≥ 2 Tasks per Run, recommended 3. Validates FR-8, FR-9. **(SHB rubric bar 2.)**
- **SM-3**: Real tool use — each Specialist Agent invokes ≥ 1 Tool with a concrete input and a concrete output during the demo Run. Target: 100% of demo Agents. Validates FR-3, FR-9. **(SHB rubric bar 3.)**
- **SM-4**: Trace Dashboard renders end-to-end — the demo Run's Audit Trail is visible as both timeline and collaboration graph, with every step explorable. Target: 0 missing steps; graph renders in < 1 s. Validates FR-21, FR-22, FR-23. **(SHB rubric bar 4.)**


**Secondary (brief stretch + platform integrity)**


- **SM-5**: Generated Mini-App with real storage — the demo Run produces a Mini-App with a live JSONB Namespace, CRUD endpoints, and an auth-gated UI that the judge can open and edit. Target: 1 live Mini-App per demo. Validates FR-12, FR-13, FR-14, FR-15.
- **SM-6**: Closed loop demonstrated — an edit on the generated Mini-App emits an App Event that triggers a follow-on Workflow Run within 5 s. Target: 1 closed-loop firing per demo. Validates FR-17, FR-19.
- **SM-7**: User-configured Model — at least one demo Agent uses a Model the team selected at config time (not a hard-coded platform default). Target: 100% of demo Agents. Validates FR-5, FR-26.


**Counter-metrics (do not optimize)**


- **SM-C1**: Agent decision latency — do NOT over-optise Orchestrator or Agent latency at the cost of Audit Trail completeness. A faster Run with missing trace entries fails SM-4 even if SM-1–SM-3 pass. Counterbalances SM-1 through SM-3.
- **SM-C2**: Demo smoke-test variance — do NOT game the demo by hard-coding outputs. A Run that produces correct outputs without invoking Tools (per Audit Trail) fails SM-3 even if the screen looks right. Counterbalances SM-3.
- **SM-C3**: Tenant isolation probe — do NOT weaken per-Tenant isolation to ship a feature faster. A cross-Tenant read attempt must return 404 in every demo Run. Counterbalances SM-5.


## 8. Constraints, Guardrails & NFRs


### 8.1 Banking Data Sensitivity


- The platform must not log raw PII (citizen ID, account number, full name) into the **Audit Trail** unless the originating Agent explicitly marks the entry as PII-safe. `[ASSUMPTION: demo data is synthetic — no real customer PII.]`
- Knowledge Base uploads must be limited to policy/regulation/SOP documents — not real customer records.
- The demo Tenant uses synthetic loan cases only.


### 8.2 Cost Guardrails


- The **Model Layer** exposes a per-Run token spend counter visible in the Trace Dashboard. `[ASSUMPTION: at least one provider exposes token counts.]`
- A Run that exceeds `[ASSUMPTION: 50,000 tokens]` emits a warning in the Trace Dashboard but is not aborted.


### 8.3 Why Now (load-bearing)


The SHB Hack CX Together 2026 problem statement verbatim:


> "Current AI use cases such as RAG and anomaly detection often remain focused on question answering or analysis. By 2026, the technology landscape is increasingly oriented toward agentic AI systems that can plan, coordinate, use tools, and take actions. Hack CX Together 2026 therefore needs a challenge that combines foundation-model capabilities with a clear multi-agent architecture and explores practical SHB applications beyond traditional RAG and chatbot solutions."


This is why the platform must ship **all four rubric bars** plus the closed loop — agent + generated app + event back. RAG-only and chatbot-only entries fail the brief.


### 8.4 Cross-Cutting NFRs


- **Performance:**
  - Orchestrator first-response (request → first Task dispatched): < 5 s p95 on demo hardware.
  - Mini-App page load: < 2 s p95.
  - Trace Dashboard render: < 1 s for any Run with ≤ 1,000 Audit Trail entries.
- **Concurrency:**
  - Platform supports ≥ 5 simultaneous Workflow Runs for the demo without degradation. `[ASSUMPTION: demo concurrency target.]`
- **Observability:**
  - Every LLM call logs `{provider, model, prompt_token_count, completion_token_count, latency_ms}` to the Audit Trail.
  - Platform logs (separate from Audit Trail) are queryable by run_id.
- **Security:**
  - Per-Tenant isolation enforced at the data layer (FR-25).
  - API Integrations use stored credentials, never hard-coded secrets in source.
  - `[NOTE FOR PM]` Production-grade secrets management is post-hackathon — see §5.
- **Reliability:**
  - Workflow Runs are resumable after a process restart (`[ASSUMPTION: Run state persisted to PostgreSQL]`).
  - Action Bus delivers App Events at-least-once (FR-20).


### 8.5 Technical Constraints (team decisions, not FRs)


Per the source brief, the team has decided:
- **Backend:** FastAPI (Python).
- **Database:** PostgreSQL with JSONB for Mini-App entity storage and Audit Trail.
- **Frontend:** ReactJS.
- **Agent/Task transport:** MCP (doubles as Task Store).
- **LLM access:** provider-agnostic Model Layer (FR-26); specific providers chosen at config time.


These are constraints on Architecture, not feature-level requirements.


## 9. Integration & Dependencies


- **LLM providers** — at least one provider's API must be available at demo time. The team brings the API key(s). `[ASSUMPTION: team supplies at least one working provider key.]`
- **MCP server** — the platform ships with an MCP server component exposing the Task Store and Tool invocation surface.
- **Embedding model** — used by KB retrieval; sourced from the same provider as the Agent's Model where possible, or a separate provider. `[ASSUMPTION: Architecture picks the embedding model.]`
- **Banking policy documents** — the team supplies 3–5 sample SHB-relevant documents (lending policy excerpt, NHNN circular excerpt, AML/KYC circular excerpt, ops SOP excerpt). `[ASSUMPTION: team brings these.]`
- **No live bank-core integration** in MVP — Integrations point at stubbed FastAPI endpoints.


## 10. Risks & Mitigations


| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R-1 | **2-day timeline insufficient for all 6 feature groups** | High | High | Strict MVP cut: pre-configure 3 Agents + 1 Workflow before demo day; builder UI can be minimal. Defer everything in §5 and §6.2. |
| R-2 | **LLM provider outage at demo time** | Low | High | Configure Agents on at least 2 providers (e.g., Anthropic + OpenAI); keep Model Layer fallback working. |
| R-3 | **Orchestrator produces inconsistent decomposition** | Medium | Medium | Cap decomposition with a max-Task ceiling; surface as human-escalation if exceeded. |
| R-4 | **MCP integration slips** | Medium | High | MCP is load-bearing; treat as Day-1 spike. If MCP integration blocks, fall back to a JSON-over-HTTP task bus with the same surface contract, marked as a known downgrade. |
| R-5 | **Mini-App auto-provisioning has a cold-start bug** | Medium | Medium | Pre-provision one Mini-App during Tenant bootstrap so the demo Run's first emission is "warm." |
| R-6 | **Trace Dashboard render blows the demo laptop** | Low | High | Profile on a 100-entry Run before demo; cache rendered graphs; cap visible entries with pagination. |
| R-7 | **Cost overrun from LLM calls during rehearsals** | Medium | Low | Use cheaper Models for specialist executors during dev; reserve premium Model for demo Run. Per-Run token counter (§8.2) keeps spend visible. |
| R-8 | **Team interpreted "any business flow" as "ship many flows"** | Medium | High | Re-state scope: platform supports any flow; demo ships ONE configured flow. Documented in §6.1 and Assumptions. |


## 11. Stakeholders & Approvals


- **Product owner:** Nguyen (PM).
- **Build team:** `[ASSUMPTION: 3–5 developers split across frontend, backend, AI/agent, design — confirm with Nguyen.]`
- **Mentor:** Named in the brief; approves success metrics post-platform (the brief explicitly defers quantitative metrics until platform-ready). `[ASSUMPTION: mentor identity to confirm.]`
- **Judges:** Hack CX Together 2026 panel — see SHB problem statement (§8.3).
- **Downstream BMad workflows:** UX (`bmad-ux`), Architecture (`bmad-architecture`), Epics & Stories (`bmad-create-epics-and-stories`).


## 12. Open Questions


1. **OQ-1.** Team size and roles — confirm 3–5 developers and the split (frontend / backend / AI-agent / design)?
2. **OQ-2.** Which LLM provider(s) will the team bring API keys for? (Anthropic, OpenAI, Google, local?)
3. **OQ-3.** Which sample policy documents will populate the demo KBs? (Team must source 3–5 SHB-relevant docs.)
4. **OQ-4.** Deployment target for judging — local laptop, single cloud VM, or SHB-provided infra?
5. **OQ-5.** Mentor identity and any mentor-imposed constraints (timelines, tech bans, infra)?
6. **OQ-6.** Sandbox technology for embedded Python Tools — Docker, gVisor, WebAssembly, or an external service like E2B? (Affects FR-3.)
7. **OQ-7.** Tenant bootstrap data — does the team prepare a single canonical demo Tenant, or multiple alt-Tenants for resilience?
8. **OQ-8.** Vietnamese-language depth — UI labels only, or also Vietnamese-language system prompts for demo Agents?
9. **OQ-9.** Token-spend ceiling per Run (placeholder in §8.2) — confirm or override.
10. **OQ-10.** Run-state persistence technology (placeholder in §8.4) — PostgreSQL-only, or Redis for transient Run state?


## 13. Assumptions Index


Every `[ASSUMPTION]` from the document, surfaced for explicit confirmation:


- **§2.1 / §2.3** — At least one LLM provider available at demo time.
- **§2.3 (UJ-2)** — Judge availability and demo format (booth vs. stage).
- **§3 (User)** — v1 roles are light: builder + manager + operator. Full RBAC deferred.
- **§4.1 / FR-2** — Document upload ceiling 20 MB.
- **§4.1 / FR-3** — Tool execution sandbox tech chosen by Architecture; 10-second execution budget.
- **§4.1 / FR-4** — For MVP, API Integrations point at stubbed endpoints (no live OAuth).
- **§4.2 / FR-9** — Retry policy: 2 retries with exponential backoff; per-Agent timeout 60 s.
- **§4.2 / FR-9** — For MVP, no streaming partial results during a Run.
- **§4.2 / FR-10** — Unresolved escalation timeout: 5 minutes.
- **§4.4 / FR-18** — Scheduler resolution: 60 s.
- **§4.5 / FR-22 / FR-23** — Demo hardware is a single laptop; graph-size ceiling 10 Specialist Agent invocations.
- **§4.5 / FR-24** — Audit signing key management deferred to Architecture.
- **§4.6 / FR-28** — Team pre-configures ≥ 3 Agents and 1 Workflow before demo day.
- **§6.1** — Same as FR-28: ≥ 3 pre-configured Agents.
- **§8.1** — Demo data is synthetic; no real customer PII.
- **§8.2** — Per-Run token ceiling placeholder: 50,000 tokens.
- **§8.4** — Demo concurrency target: ≥ 5 simultaneous Runs.
- **§8.4** — Run state persisted to PostgreSQL.
- **§9** — Team supplies at least one working provider key.
- **§9** — Architecture picks the embedding model.
- **§9** — Team supplies 3–5 sample SHB-relevant policy documents.
- **§11** — Team size 3–5; mentor identity to confirm.


---


*Draft v1 — Fast path. `[ASSUMPTION]` tags and Open Questions surfaced for Nguyen's review. Next step: Nguyen confirms/overrides assumptions, then we walk Finalize (memlog audit, reconcile against brief + problem statement, optional reviewer gate, triage open items, polish, close).*


---


## Finalization


**Status:** `final` (set 2026-07-17).
**Mode:** Fast path, hackathon stakes. Content shipped as-drafted per PM sign-off ("ship as is").
**Skipped per Fast path / PM instruction:** reviewer gate, editorial polish pass, formal input-reconciliation subagents. The source brief (`_bmad-output/planning-artifacts/briefs/brief-VAIC-2026-07-17/brief.md`) and the SHB Hack CX Together 2026 problem statement were the inputs; both are reflected verbatim in §1, §7, and §8.3.
**Open items carried forward:** 22 `[ASSUMPTION]` tags (§13) and 10 Open Questions (§12) are explicitly NOT resolved — they are the next conversation, not blockers for v1 build kickoff. Architecture, UX, and Epics workflows consume these as inputs.
**Next-step routing:** see §11 Stakeholders and the "Next steps" block in the chat that closed this run.




---


# Appendix A: Addendum


> Schemas, data sketches, and examples referenced by FRs throughout the PRD. Section IDs preserved: A1 ↔ FR-8, A2 ↔ FR-25/FR-13, A3 ↔ FR-16/FR-14/FR-15, A4 ↔ FR-3, A5 ↔ FR-17/FR-19, A6 ↔ SM-2/UJ-1, A7 ↔ FR-22/FR-23, A8 ↔ FR-28. Originally authored as a separate companion file; merged on 2026-07-17.


> Depth that belongs in downstream documents (Architecture, Solution Design, UX spec) or earned a place but does not fit the PRD's capability framing. The PRD references sections here by ID (e.g., "see addendum §A1").


## A1. Task Schema (referenced by FR-8)


The **Task Schema** is the JSON/YAML contract every Task emitted by the Orchestrator conforms to.


```yaml
task:                     # human-readable summary, ≤ 120 chars
  summary: "Verify applicant's financial ratios against lending policy"


target_agent_id:          # UUID; must resolve to a Specialist Agent in the Run's Tenant
  "..."
input:                    # JSON Schema-validated object the target Agent receives
  financial_summary:
    revenue: 12000000000  # VND
    # ...


output:                   # declared output shape, used by Orchestrator at aggregation
  type: object
  properties:
    verdict: { enum: [pass, fail, review] }
    ratios: { type: object }
    rationale: { type: string }


expected:                 # what the Orchestrator expects the Agent to do
  - "Retrieve relevant lending-policy clauses via KB"
  - "Compute three financial ratios"
  - "Compare each ratio against the policy threshold"
  - "Return a verdict with rationale"


criteria:                 # rubric the Agent's response is evaluated against
  confidence_floor: 0.7
  must_cite_kb: true
  must_use_tool: "financial-ratio-calculator"
```


Rejected Tasks (schema-invalid) are dropped and logged. Tasks with `target_agent_id` outside the Run's Tenant or Department scope are rejected before dispatch.


## A2. Multi-Tenancy Data Model Sketch (referenced by FR-25, FR-13)


Logical row shape (every persisted record carries these four fields):


```
tenant_id        UUID NOT NULL
department_id    UUID NOT NULL
owner_id         UUID          -- nullable for system-generated rows
visibility_tier  ENUM(public, need_auth, private) NOT NULL
+ domain columns
```


Tables (indicative — Architecture owns the final):


- `tenants(id, name, created_at, audit_key_id)`
- `departments(id, tenant_id, name)`
- `users(id, tenant_id, email, role)`
- `agents(id, tenant_id, department_id, owner_id, name, system_prompt, model_ref, kb_id, version)`
- `agent_tools(id, agent_id, name, input_schema, output_schema, embedded_python_ref)`
- `agent_api_integrations(id, agent_id, name, base_url, auth_ref)`
- `kbs(id, tenant_id, department_id, owner_id)`
- `kb_documents(id, kb_id, mime, source_uri, chunk_count)`
- `kb_chunks(id, document_id, ordinal, embedding, text)`
- `workflows(id, tenant_id, name, description, version)`
- `workflow_runs(id, workflow_id, tenant_id, status, request, started_at, ended_at)`
- `tasks(id, run_id, target_agent_id, schema_payload, status)`
- `audit_trail(id, run_id, step_id, agent_id, type, input, output, latency_ms, model, ts)` — append-only
- `mini_apps(id, tenant_id, department_id, owner_id, name, entity_schema, ui_spec, visibility_tier, namespace_table)`
- `mini_app_rows` — a JSONB table per app, OR a single JSONB-backed table with `app_id` discriminator (Architecture decides).
- `actions(id, tenant_id, type, cron_or_filter, target_workflow_id, status)`
- `app_events(id, app_id, tenant_id, sequence_no, event_type, payload, ts)` — sequence_no per app_id


## A3. Visibility Tier Access Matrix (referenced by FR-16, FR-14, FR-15)


| Requester | `Public` Mini-App | `Need-Auth` Mini-App | `Private` Mini-App |
|-----------|-------------------|----------------------|---------------------|
| Anonymous | 401 | 401 | 401 |
| Same Tenant, different Department | 200 (read) | 403 | 403 |
| Same Tenant, same Department, not whitelisted | 200 (read) | 200 | 403 |
| Same Tenant, same Department, whitelisted | 200 | 200 | 200 |
| Cross-Tenant | 404 | 404 | 404 |


404 (not 403) on cross-Tenant access is intentional — never confirm a Mini-App's existence to a caller outside its Tenant.


## A4. Tool Configuration Schema (referenced by FR-3)


```yaml
name: "financial-ratio-calculator"
description: "Computes DSCR, current ratio, debt-to-equity from a financial summary."


header:
  auth: bearer            # or basic, api_key, none
  token_ref: "vault://tools/fr-calc"   # secrets via env / vault, never inline


input_schema:             # JSON Schema
  type: object
  required: [financial_summary]
  properties:
    financial_summary: { type: object }


output_schema:
  type: object
  required: [ratios, verdict]
  properties:
    ratios: { type: object }
    verdict: { enum: [pass, fail, review] }


embedded_python:          # optional, for tighter control
  source_ref: "tools/fr_calc.py"
  entry: compute_ratios
  network: false
  execution_budget_s: 10
```


Tool invocations that fail input validation are rejected before execution. Tool outputs that fail output validation are logged in the Audit Trail and surfaced as failed steps in the Trace Dashboard.


## A5. App Event Envelope (referenced by FR-17, FR-19)


```json
{
  "event_id": "uuid",
  "app_id": "uuid",
  "tenant_id": "uuid",
  "department_id": "uuid",
  "actor_user_id": "uuid | null",
  "sequence_no": 42,
  "event_type": "row.created | row.updated | row.deleted",
  "payload": { /* event-specific */ },
  "ts": "2026-07-17T08:34:12.123Z"
}
```


Event Triggers filter on `(app_id, event_type, optional JSON-path predicate on payload)`.


## A6. Orchestrator Decomposition — Example Run (referenced by SM-2, UJ-1)


Request: *"Pre-screen business loan application #LOAN-2026-0143 for Acme Trading JSC."*


Orchestrator decomposition (illustrative — actual decomposition is dynamic per request, per FR-8):


1. Task → Credit Analyst Agent
   - `task`: "Compute financial ratios and verdict against lending policy for Acme Trading."
   - `expected`: ["retrieve policy clauses", "compute ratios", "compare to thresholds", "return verdict"]
   - `criteria`: { confidence_floor: 0.7, must_cite_kb: true, must_use_tool: "financial-ratio-calculator" }


2. Task → Compliance Analyst Agent
   - `task`: "Run KYC/AML screen on Acme Trading principals."
   - `expected`: ["screen against sanctions list", "retrieve KYC/AML circular", "return flags"]
   - `criteria`: { confidence_floor: 0.85, must_cite_kb: true, must_use_tool: "sanctions-check" }


3. Task → Operations Analyst Agent
   - `task`: "Verify document checklist completeness for the loan application."
   - `expected`: ["read checklist", "match against provided documents", "return gaps"]
   - `criteria`: { confidence_floor: 0.9, must_use_tool: "doc-checklist-verifier" }


Aggregation → Mini-App emission (FR-12) → "Business Loan Pre-Screen Case" Mini-App provisioned (FR-13–FR-15) with one row carrying the consolidated decision.


Closed-loop demo (SM-6): a User edits a field in the Mini-App → App Event `row.updated` fires → Event Trigger kicks a follow-on "Post-Filing Workflow."


## A7. Trace Dashboard Views (referenced by FR-22, FR-23)


Two alternate views over the same Audit Trail:


- **Timeline view (FR-22):** vertical list of step cards. Each card: `{step_id, agent, type, latency_ms, expand → {input, output, model}}`. Default view.
- **Collaboration graph view (FR-23):** Orchestrator node at top, Specialist Agent nodes below, edges labelled `{task_summary, status}`. Toggled view.


Both views read the same Audit Trail; they differ only in presentation.


## A8. Bootstrapping the Demo Tenant (referenced by FR-28)


A script (`scripts/bootstrap_demo_tenant.py` or equivalent) provisions:


- 1 Tenant ("SHB Demo Bank")
- 3 Departments (Credit, Legal/Compliance, Operations)
- 3 Users (one per role: builder, manager, operator)
- 3 Specialist Agents (Credit Analyst, Compliance Analyst, Operations Analyst), each with:
  - A KB seeded from sample policy PDFs
  - 1–2 Tools registered (per §A6)
  - A Model selected at config time
- 1 Workflow ("Business Loan Pre-Screen") with the description that triggers the §A6 decomposition
- 1 pre-provisioned Mini-App ("Business Loan Pre-Screen Case") for cold-start safety (R-5)


The script is idempotent and runs in < 60 s on demo hardware.


---


*Addendum v1. Mechanism and technical-how depth referenced from the PRD. Architecture work may move, refine, or replace any of these; the PRD's capability-level FRs are the contract.*




