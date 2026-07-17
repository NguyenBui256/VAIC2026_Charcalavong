# Design Paradigm

**Hexagonal modular monolith.** One FastAPI process composed of bounded modules aligned to the PRD's feature groups. Inside each module, domain logic sits at the center and all I/O (HTTP, DB, LLM providers, MCP tools, sandboxes) flows through ports. Hexagonal because the Model Layer (FR-26), Tools (FR-3), and MCP integration are inherently ports-and-adapters shapes — naming the pattern loads the whole model. Modular monolith because two days, one team, one deploy; the module seams make future microservice extraction trivial if ever needed.

```text
backend/app/modules/
  tenant/          # FR-25, FR-28, identity
  agent_builder/   # FR-1..FR-6
  orchestrator/    # FR-7..FR-11
  mini_app/        # FR-12..FR-17
  actions/         # FR-18..FR-20
  audit/           # FR-21..FR-24
backend/app/core/
  ports/           # LlmPort, ToolPort, AuditPort, McpClientPort, DocIntakePort
  adapters/        # anthropic, openai, google, ollama, mcp_client, sandbox
```
