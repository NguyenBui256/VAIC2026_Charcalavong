# Closed loop — the load-bearing flow

```mermaid
flowchart LR
    Req[User submits request] --> Orch[Orchestrator<br/>decomposes]
    Orch -->|INSERT tasks| DB[(tasks table)]
    DB --> A1[Credit Agent]
    DB --> A2[Compliance Agent]
    DB --> A3[Operations Agent]
    A1 & A2 & A3 -->|via McpClientPort| Mcp[MCP tools<br/>rag · gmail · calendar]
    A1 & A2 & A3 -->|via LlmPort| LLM[LLM providers]
    A1 & A2 & A3 -->|results| Agg[Orchestrator aggregates]
    Agg -->|emit schema| Prov[Mini-App Provisioner]
    Prov --> Store[(JSONB namespace<br/>+ CRUD + UI)]
    User[User edits row] -->|UI| Store
    Store -->|emit App Event| Bus[(Action Bus)]
    Bus -->|Event Trigger| NextReq[Follow-on Workflow Run]
    NextReq --> Orch

    classDef appendOnly fill:#fee,stroke:#c33
    classDef external fill:#eef,stroke:#336
    class DB,Store,Bus appendOnly
    class Mcp,LLM external
```

This is what makes VAIC architecturally novel — agent generates app → app emits events → agents react. Every arrow in this diagram is governed by an AD: Orchestrator→tasks (AD-6), Agent→MCP tools (AD-3), Agent→LLM (AD-7), Aggregation→Provisioner (AD-8), Mini-App→Bus (AD-9).
