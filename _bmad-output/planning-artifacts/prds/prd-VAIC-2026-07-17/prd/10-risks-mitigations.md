# 10. Risks & Mitigations

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
