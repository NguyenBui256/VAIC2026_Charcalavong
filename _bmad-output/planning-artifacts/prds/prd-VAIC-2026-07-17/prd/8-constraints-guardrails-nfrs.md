# 8. Constraints, Guardrails & NFRs

## 8.1 Banking Data Sensitivity

- The platform must not log raw PII (citizen ID, account number, full name) into the **Audit Trail** unless the originating Agent explicitly marks the entry as PII-safe. `[ASSUMPTION: demo data is synthetic — no real customer PII.]`
- Knowledge Base uploads must be limited to policy/regulation/SOP documents — not real customer records.
- The demo Tenant uses synthetic loan cases only.

## 8.2 Cost Guardrails

- The **Model Layer** exposes a per-Run token spend counter visible in the Trace Dashboard. `[ASSUMPTION: at least one provider exposes token counts.]`
- A Run that exceeds `[ASSUMPTION: 50,000 tokens]` emits a warning in the Trace Dashboard but is not aborted.

## 8.3 Why Now (load-bearing)

The SHB Hack CX Together 2026 problem statement verbatim:

> "Current AI use cases such as RAG and anomaly detection often remain focused on question answering or analysis. By 2026, the technology landscape is increasingly oriented toward agentic AI systems that can plan, coordinate, use tools, and take actions. Hack CX Together 2026 therefore needs a challenge that combines foundation-model capabilities with a clear multi-agent architecture and explores practical SHB applications beyond traditional RAG and chatbot solutions."

This is why the platform must ship **all four rubric bars** plus the closed loop — agent + generated app + event back. RAG-only and chatbot-only entries fail the brief.

## 8.4 Cross-Cutting NFRs

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

## 8.5 Technical Constraints (team decisions, not FRs)

Per the source brief, the team has decided:
- **Backend:** FastAPI (Python).
- **Database:** PostgreSQL with JSONB for Mini-App entity storage and Audit Trail.
- **Frontend:** ReactJS.
- **Agent/Task transport:** MCP (doubles as Task Store).
- **LLM access:** provider-agnostic Model Layer (FR-26); specific providers chosen at config time.

These are constraints on Architecture, not feature-level requirements.
