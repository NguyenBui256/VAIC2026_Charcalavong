# Deferred

Decisions and dimensions this altitude intentionally does **not** fix — each can wait for the reason given. Anything smelling like future-proofing landed here rather than as an AD.

- **Per-Model token spend counter UI** (PRD §8.2) — log the data in `audit_trail` now; surface in the Trace Dashboard only if a demo rehearsal shows the rubric wants it.
- **Streaming partial Agent responses** — PRD §5 non-goal; arq workers complete then surface.
- **Visual drag-drop Workflow editor** — PRD §5 non-goal.
- **Exactly-once App Event delivery** — PRD §5 non-goal; at-least-once with sequence numbers is the contract.
- **Stronger embedded-Python sandbox** — wasmtime-py / E2B replaces subprocess approach when a Tool actually needs it.
- **Per-tenant encryption at rest** — post-hackathon.
- **Multi-region deployment** — single-region for MVP.
- **Cross-Tenant Mini-App marketplace** — PRD §5 non-goal.
- **Webhook ingress for Event Triggers** — only internal App Events fire Workflows for MVP.
- **Audit Trail archival** — keep last 7 days for demo (PRD §6.2 assumption).
- **pgvector / VAIC-side retrieval** — pending FR-2 reconciliation. If the parallel-team MCP server owns all retrieval, VAIC has no vector store.
- **Per-module extraction to microservices** — seams preserved by AD-1; not needed for hackathon.
- **Full RBAC engine** — builder + manager + operator only for v1 (PRD assumption).
- **Vietnamese-language UI depth** — labels only for MVP (PRD assumption).
- **Agent fine-tuning / training** — out of v1.
- **C4 diagram set / solution-design prose** — only if a mentor review asks for it.
