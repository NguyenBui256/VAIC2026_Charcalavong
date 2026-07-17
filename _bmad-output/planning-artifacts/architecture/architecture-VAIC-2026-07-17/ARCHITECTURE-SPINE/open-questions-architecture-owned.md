# Open Questions (Architecture-owned)

These were deferred from the PRD or surfaced by this run. Each has a revisit condition in the memlog.

1. **FR-2 reconciliation.** PRD FR-2 says "The platform chunks, embeds, indexes, and serves retrieval." User correction: `rag.search` is an MCP tool owned by the parallel team. **Does VAIC upload documents to the MCP server via an admin tool, or does VAIC hold its own document store and pass a department-scoped namespace ID to `rag.search`?** Affects whether `pgvector` is in the stack at all. *Revisit: before Agent Builder epics start.*
2. **FR-4 reconciliation.** With Gmail and Calendar as MCP tools, does FR-4 (API Integration as a distinct concept) survive, or do all "integrations" become MCP tool registrations? Recommend collapsing FR-4 into FR-3 for MVP. *Revisit: when scoping Agent Builder stories.*
3. **MCP server contract.** What's the exact tool list, input/output schemas, and auth model the parallel team exposes? Architecture needs the MCP server's tool catalog as a contract before Agent Builder epics start. *Revisit: as soon as the parallel team publishes a tool list.*
4. **MCP server outage behavior.** AD-3 says "VAIC must survive" — but what does the Workflow Run do when an MCP tool call fails? Retry budget, fallback, or fail the Run? *Revisit: when designing FR-9 error paths.*
5. **Department isolation on MCP side.** If the MCP server owns retrieval (FR-2), how does it enforce that a Credit Agent's `rag.search` call can't see an HR department's documents? VAIC's RLS doesn't reach into the MCP server. *Revisit: with the parallel team — likely a namespace parameter on `rag.search`.*
6. **Audit Trail signing key.** PRD assumption defers to Architecture. Recommendation: HMAC with a per-tenant key stored in `tenants.audit_key_id` → `audit_keys` table; signature in `audit_trail.signature`. Minimal crypto, sufficient for demo. *Revisit: when implementing FR-24 export.*
