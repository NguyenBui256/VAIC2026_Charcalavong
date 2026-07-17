# 2. Target User

## 2.1 Jobs To Be Done

**Primary users — bank employees and managers running cross-department work daily:**
- "Help me move this loan application through Credit, Legal, and Operations without me chasing each desk."
- "Help me capture the decision trail on this exception so audit can reconstruct it next quarter."
- "Help me turn a flow my team runs on Excel every week into a small app my team actually operates — without filing an IT ticket."

**Secondary users — IT / internal-tools teams:**
- "Help me give the business a way to ship its own automation without my team being the bottleneck."

**Builder (hackathon context):**
- "Help me prove at demo time that the platform is real — that any flow can be configured and run, not a hard-coded demo."

## 2.2 Non-Users (v1)

- **End customers of the bank** — retail and corporate customers are *not* direct VAIC users in v1. They may be the *subject* of a workflow (e.g., a loan applicant) but never the operator.
- **External developers / third-party integrators** — VAIC is configured by the bank's own staff and IT, not exposed as a public platform-as-a-service in v1. `[NON-GOAL for MVP]`
- **Regulators / auditors as direct users** — they consume **Audit Trails** produced by VAIC, but do not operate VAIC directly in v1.

## 2.3 Key User Journeys

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
