# 9. Integration & Dependencies

- **LLM providers** — at least one provider's API must be available at demo time. The team brings the API key(s). `[ASSUMPTION: team supplies at least one working provider key.]`
- **MCP server** — the platform ships with an MCP server component exposing the Task Store and Tool invocation surface.
- **Embedding model** — used by KB retrieval; sourced from the same provider as the Agent's Model where possible, or a separate provider. `[ASSUMPTION: Architecture picks the embedding model.]`
- **Banking policy documents** — the team supplies 3–5 sample SHB-relevant documents (lending policy excerpt, NHNN circular excerpt, AML/KYC circular excerpt, ops SOP excerpt). `[ASSUMPTION: team brings these.]`
- **No live bank-core integration** in MVP — Integrations point at stubbed FastAPI endpoints.
