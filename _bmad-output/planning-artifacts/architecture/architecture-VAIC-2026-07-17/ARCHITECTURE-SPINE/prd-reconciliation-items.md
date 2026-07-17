# PRD Reconciliation Items

The spine surfaced contradictions between the user's mid-run corrections and the finalized PRD. These are flagged for a follow-up `bmad-edit-prd` run, **not** blockers for the build:

- **PRD §9** claims "the platform ships with an MCP server component exposing the Task Store and Tool invocation surface." Reality: VAIC is an MCP client; the parallel team ships the server. **Suggest: rewrite §9 to reflect VAIC as MCP client.**
- **PRD FR-2** claims VAIC chunks/embeds/indexes/serves. Reality (per user): the parallel team owns `rag.search`. **Suggest: split FR-2 into FR-2a (intake + department tagging — VAIC) and FR-2b (retrieval — MCP server).**
- **PRD FR-4** (API Integration as VAIC-side stubbed endpoints). Reality (per user): Gmail/Calendar are MCP tools. **Suggest: collapse FR-4 into FR-3 or mark as non-goal for MVP.**
- **PRD FR-9** "MCP also serves as the shared Task Store." Reality: VAIC's Task state is Postgres-internal. **Suggest: rewrite FR-9 to reflect MCP as tool-protocol only.**

These don't block implementation — the spine is the build contract. They block the *next* PRD finalization pass.


---
