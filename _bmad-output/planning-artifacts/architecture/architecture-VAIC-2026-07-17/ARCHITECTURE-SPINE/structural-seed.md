# Structural Seed

```text
vaic/
  backend/
    app/
      main.py                    # FastAPI app, middleware, route registration
      modules/
        tenant/                  # FR-25, FR-28, identity
          routes.py
          service.py
          models.py
        agent_builder/           # FR-1..FR-6
          routes.py
          service.py
          models.py
        orchestrator/            # FR-7..FR-11
          routes.py
          service.py             # decomposition, dispatch, aggregate
          models.py              # workflows, workflow_runs, tasks
        mini_app/                # FR-12..FR-17
          routes.py              # auto-gen CRUD endpoints (mounted per app)
          provisioner.py         # the pure function (AD-8)
          models.py
          ui_renderer.py         # emits React route from UI spec
        actions/                 # FR-18..FR-20
          routes.py
          bus.py                 # arq-backed Action Bus
          triggers.py            # Schedule + Event triggers
        audit/                   # FR-21..FR-24
          routes.py              # trace dashboard API, export
          sink.py                # the only writer (AD-4)
      core/
        ports/
          llm.py                 # LlmPort
          tool.py                # ToolPort (MCP + embedded-Python unified)
          audit.py               # audit.log() entry point
          mcp_client.py          # McpClientPort
          doc_intake.py          # document upload → parallel-team MCP server
        adapters/
          anthropic.py
          openai.py
          google.py
          ollama.py
          mcp_client.py
          sandbox.py             # subprocess runner for embedded Python
        tenant_context.py        # contextvars + middleware
        errors.py                # error envelope
      bootstrap/
        seed_demo_tenant.py      # FR-28 + addendum §A8
    scripts/
      bootstrap_demo_tenant.py
    tests/
      unit/
      integration/
      e2e/
    pyproject.toml
    alembic.ini
  frontend/
    src/
      routes/                    # file-based routing (TanStack Router or React Router)
        agent-builder/
        orchestrator/
        mini-apps.$appId/        # dynamic Mini-App UIs (FR-15)
        trace.$runId/            # Trace Dashboard (FR-22, FR-23)
        actions/
      components/
      hooks/
      lib/
    vite.config.ts
    package.json
  infra/
    docker-compose.yml           # postgres, redis
  docs/
```
