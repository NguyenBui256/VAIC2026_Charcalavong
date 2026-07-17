# Dimensions Entirely Silent at This Altitude

The following operational dimensions are not covered by any AD, Convention, or Deferred item. They may be intentionally out of altitude scope, but noting them for completeness:

1. **Deployment topology.** The spine says "one FastAPI process" but the Async Jobs convention says "arq only — background Workflow Run execution." arq runs in a separate process (`arq Worker`). The spine doesn't specify: one web process + one worker process? Multiple workers? How is the FastAPI app shared between them (it isn't — they're different entrypoints)?

2. **Database connection pooling across web vs worker.** SQLAlchemy sync engine with a connection pool — the pool config, pool size, and whether the worker reuses the same engine or creates its own, are unspecified. This interacts with Divergence 1 (tenant context must be set per-connection or per-query in the worker).

3. **Observability beyond audit.** AD-4 covers audit trail (domain events). There is no mention of: structured logging (JSON logs?), metrics (Prometheus?), health checks (/health, /ready), or distributed tracing (OpenTelemetry). For a hackathon demo this is likely fine, but the spine should at least list it as Deferred.

4. **Graceful shutdown and in-flight Run handling.** AD-6 says workers poll `pending` runs on startup. What about shutdown? If a worker is killed mid-Run, the Run stays `running` forever. No timeout or reaper mechanism is defined for stuck `running` Runs. The escalation timeout (5 min) only covers `awaiting_human`, not `running`.

5. **Database migration strategy for Mini-App namespaces.** AD-8 says the Provisioner creates "JSONB namespace + CRUD endpoints." This implies dynamic table or JSONB column creation. If a Mini-App schema changes (new columns), what migrates the existing data? No AD covers Mini-App schema evolution.

6. **MCP client retry and timeout.** AD-3 and Open Question 4 acknowledge MCP outage behavior is undefined, but the spine doesn't set even a default timeout for MCP calls. A hung MCP server will stall a Run indefinitely (no `running` timeout per finding #4 above).

---
