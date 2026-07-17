# 6. MVP Scope

## 6.1 In Scope (Demo-Scoped Platform)

All six feature groups (§4.1–§4.6) ship in working form for the demo:

- **Agent Builder** — full CRUD; at least 3 pre-configured Specialist Agents in the demo Tenant (suggested: Credit Analyst, Compliance Analyst, Operations Analyst — but the platform supports any configuration). `[ASSUMPTION: team will pre-configure at least 3 to satisfy rubric bar 1]`
- **Workflow Orchestrator** — full decomposition + MCP dispatch + aggregation + human escalation; at least 1 pre-configured Workflow in the demo Tenant.
- **Mini-App Builder** — auto-provisioning live; at least 1 Mini-App generated live during the demo Run.
- **Actions** — Schedule Trigger and Event Trigger both functional; at least 1 Event Trigger firing during the demo (Mini-App → Workflow).
- **Audit, Trace & Decision Provenance** — full Audit Trail logging; Trace Dashboard rendering both timeline and collaboration graph views.
- **Platform Foundation** — single-Tenant demo, multi-Department, Model Layer working with at least one provider, React SPA, Tenant bootstrap script.

## 6.2 Out of Scope for MVP (v2+)

- Everything in §5.
- **Vietnamese-language UI** beyond labels — agent output language is prompt-controlled, not platform-enforced.
- **Webhook ingress** — only internal App Events trigger Workflows for MVP.
- **Mini-App theming / branding controls.**
- **Audit Trail archival to cold storage.** Demo keeps the last 7 days. `[ASSUMPTION: retention window]`
- **Multi-Model routing per Agent** (one Model per Agent for MVP; routing across Models per query is v2).
- **Agent fine-tuning / training.**
- **Benchmark-vs-chatbot side-by-side** (brief marked this stretch; not scored by rubric — deferred).
