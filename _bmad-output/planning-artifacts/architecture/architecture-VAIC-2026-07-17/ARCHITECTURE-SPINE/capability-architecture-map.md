# Capability → Architecture Map

| Capability / Area | Lives in | Governed by |
| --- | --- | --- |
| FR-1 Create Agent | `agent_builder/service.py` | AD-1, AD-2 |
| FR-2 Per-Agent KB (intake half) | `agent_builder/service.py` + `core/ports/doc_intake.py` | AD-2, AD-11; FR-2 split pending reconciliation |
| FR-3 Per-Agent Tool config | `agent_builder/service.py` + `core/ports/tool.py` | AD-1, AD-3, AD-11 |
| FR-4 API Integration | `agent_builder/service.py` | AD-3; **likely collapses** — Gmail/Calendar are MCP tools |
| FR-5 Per-Agent Model selection | `agent_builder/service.py` + `core/ports/llm.py` | AD-7 |
| FR-6 Ownership & Department scoping | `agent_builder/service.py` + RLS + `McpClientPort` scope check | AD-2, AD-11 |
| FR-7 Workflow definition | `orchestrator/service.py` | AD-6 |
| FR-8 Dynamic decomposition | `orchestrator/service.py` (LLM-driven planner prompt) | AD-6, AD-7 |
| FR-9 Task dispatch & aggregation | `orchestrator/service.py` (arq worker path) | AD-3, AD-6, AD-10 |
| FR-10 Human escalation | `orchestrator/service.py` | AD-6 |
| FR-11 Per-step feedback | `orchestrator/service.py` + `audit/sink.py` | AD-4, AD-6 |
| FR-12 Schema + UI spec emission | `orchestrator/service.py` | AD-8 |
| FR-13 JSONB namespace provisioning | `mini_app/provisioner.py` | AD-5, AD-8 |
| FR-14 CRUD endpoints | `mini_app/routes.py` | AD-5, AD-8 |
| FR-15 Auth-gated UI | `frontend/routes/mini-apps.$appId/` + `mini_app/ui_renderer.py` | AD-5 |
| FR-16 Visibility Tier enforcement | RLS on `mini_app_rows` | AD-5 |
| FR-17 App Event emission | `mini_app/routes.py` → `actions/bus.py` | AD-8, AD-9 |
| FR-18 Schedule Trigger | `actions/triggers.py` (arq `cron_jobs`, per-tenant fan-out) | AD-9, AD-10 |
| FR-19 Event Trigger | `actions/triggers.py` (worker re-sets tenant context from payload) | AD-9, AD-10 |
| FR-20 Action Bus reliability | `actions/bus.py` (arq at-least-once) | AD-9 |
| FR-21 Audit Trail logging | `audit/sink.py` | AD-4 |
| FR-22 Trace timeline | `audit/routes.py` + `frontend/routes/trace.$runId/` | AD-4 |
| FR-23 Trace collaboration graph | `audit/routes.py` + frontend | AD-4 |
| FR-24 Audit export | `audit/routes.py` | AD-4 |
| FR-25 Multi-Tenant isolation | RLS on every table | AD-2 |
| FR-26 Model Layer | `core/ports/llm.py` + `core/adapters/*` | AD-7 |
| FR-27 React SPA | `frontend/` | AD-1 |
| FR-28 Tenant bootstrap | `bootstrap/seed_demo_tenant.py` | AD-2 |
