# Dependency direction

```mermaid
flowchart TB
    subgraph external[External — built by parallel team]
      McpServer[MCP Server<br/>rag.search · gmail.send · calendar.write]
    end

    subgraph vaic[VAIC — this system]
      FE[React SPA<br/>FR-27]
      API[FastAPI routes]
      TenantMod[tenant]
      AgentMod[agent_builder]
      OrchMod[orchestrator]
      MiniMod[mini_app]
      ActMod[actions]
      AudMod[audit]
      Core[core/ports + adapters]
      DB[(Postgres + RLS)]
      Bus[(arq + Redis<br/>Action Bus)]
    end

    LLMs[Anthropic · OpenAI · Google · Ollama]

    FE --> API
    API --> TenantMod & AgentMod & OrchMod & MiniMod & ActMod & AudMod
    TenantMod & AgentMod & OrchMod & MiniMod & ActMod --> Core
    Core --> DB
    Core --> Bus
    Core -.tool calls.-> McpServer
    Core -.LLM calls.-> LLMs
    AudMod --> DB
```

The dependency arrows point **inward to ports, outward to adapters**. Modules never depend on each other's internals; they call through `core/ports/`. The MCP server and LLM providers are leaves — adapters only, never imported by domain code.
