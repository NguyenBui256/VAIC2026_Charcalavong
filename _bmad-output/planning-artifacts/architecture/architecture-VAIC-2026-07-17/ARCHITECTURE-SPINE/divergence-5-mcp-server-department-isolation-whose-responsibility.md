# Divergence 5 — MCP Server Department Isolation: Whose Responsibility?

**Severity:** HIGH

**Unit A:** `orchestrator` module calls `McpClientPort.call("rag.search", {"query": "...", "department": "credit"})`. The McpClientPort adapter sends this to the external MCP server.

**Unit B:** The external MCP server receives `rag.search` with `department: "credit"` and returns documents. But AD-3 says "the MCP server itself is out of scope — VAIC does not build, host, or own it." Open Question 5 asks "how does it enforce that a Credit Agent's `rag.search` call can't see an HR department's documents?" but provides no answer.

**AD each obeys:**
- AD-3: VAIC is an MCP client; tools invoked through `McpClientPort`.
- AD-2: RLS enforces tenant isolation at the Postgres layer.

**Where they diverge:** AD-2 guarantees isolation inside VAIC's Postgres. AD-3 explicitly excludes the MCP server from VAIC's scope. No AD bridges the gap. If the MCP server doesn't enforce department isolation (or if the `department` parameter is optional and an Agent omits it), a Credit Agent can retrieve HR documents through `rag.search`. VAIC's RLS is useless here because the data left VAIC's boundary. Two builders could implement the `McpClientPort.call` with completely different assumptions: one always passes `department`, the other doesn't. Both comply with AD-3.

**Proposed fix:** New AD.

**New AD-10 — MCP Tool calls must carry department scope; VAIC enforces client-side**

> - **Binds:** FR-3, FR-6, AD-3
> - **Prevents:** cross-department data leakage through MCP tools that VAIC's RLS cannot reach
> - **Rule:** Every `McpClientPort.call` MUST include the calling Agent's `department_id` as a parameter (or in a tool-call header if the MCP protocol supports it). The `McpClientPort` adapter enforces this: if the caller does not supply `department_id`, the adapter raises a `DomainError`. VAIC cannot control what the MCP server does with it, but VAIC guarantees it always sends the scope. This is a client-side guard, not a substitute for server-side enforcement — Open Question 5 remains with the parallel team.

---
