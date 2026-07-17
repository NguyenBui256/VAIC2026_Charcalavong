# A2. Multi-Tenancy Data Model Sketch (referenced by FR-25, FR-13)

Logical row shape (every persisted record carries these four fields):

```
tenant_id        UUID NOT NULL
department_id    UUID NOT NULL
owner_id         UUID          -- nullable for system-generated rows
visibility_tier  ENUM(public, need_auth, private) NOT NULL
+ domain columns
```

Tables (indicative — Architecture owns the final):

- `tenants(id, name, created_at, audit_key_id)`
- `departments(id, tenant_id, name)`
- `users(id, tenant_id, email, role)`
- `agents(id, tenant_id, department_id, owner_id, name, system_prompt, model_ref, kb_id, version)`
- `agent_tools(id, agent_id, name, input_schema, output_schema, embedded_python_ref)`
- `agent_api_integrations(id, agent_id, name, base_url, auth_ref)`
- `kbs(id, tenant_id, department_id, owner_id)`
- `kb_documents(id, kb_id, mime, source_uri, chunk_count)`
- `kb_chunks(id, document_id, ordinal, embedding, text)`
- `workflows(id, tenant_id, name, description, version)`
- `workflow_runs(id, workflow_id, tenant_id, status, request, started_at, ended_at)`
- `tasks(id, run_id, target_agent_id, schema_payload, status)`
- `audit_trail(id, run_id, step_id, agent_id, type, input, output, latency_ms, model, ts)` — append-only
- `mini_apps(id, tenant_id, department_id, owner_id, name, entity_schema, ui_spec, visibility_tier, namespace_table)`
- `mini_app_rows` — a JSONB table per app, OR a single JSONB-backed table with `app_id` discriminator (Architecture decides).
- `actions(id, tenant_id, type, cron_or_filter, target_workflow_id, status)`
- `app_events(id, app_id, tenant_id, sequence_no, event_type, payload, ts)` — sequence_no per app_id
