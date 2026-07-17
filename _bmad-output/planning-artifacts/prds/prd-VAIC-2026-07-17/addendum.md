---
title: VAIC PRD — Addendum
parent: prd.md
created: 2026-07-17
updated: 2026-07-17
---

# VAIC PRD — Addendum

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
