# Codebase Summary — VAIC

> Living doc. Cập nhật gần nhất: 2026-07-18 (PR #1 — Epic 6 Trace + Epic 7 seed).
> Stack: FastAPI + SQLAlchemy 2.x + Postgres (RLS) · React 19 + Vite + TanStack
> Query + react-router 7. Hexagonal (ports/adapters, AD-1). Tenant isolation qua
> Postgres RLS (AD-2). Audit append-only qua một sink duy nhất (AD-4).

## Backend (`backend/app`)

### core
| File | Vai trò |
|------|---------|
| `db.py` | `Base`, `SessionLocal` (runtime, RLS), `AdminSessionLocal` (BYPASSRLS cho seed/sweep) |
| `deps.py` | `get_tenant_session` (set `app.tenant_id` + `assume_app_role`), `crud_audit_ids` (OQ-1 stopgap), `get_mcp_client` |
| `auth.py` | `AuthMiddleware` (populate `request.state`), `hash_password` |
| `errors.py` | `DomainError` hierarchy + exception handlers; envelope `{data,error,meta}` |
| `ids.py` | `uuid7` (AR-14) |
| `tenant_context.py` | `tenant_context` ContextVar + `set_tenant_session_var` |
| `settings.py`, `crypto.py`, `model_catalog.py` | config; Fernet; provider/model catalog |
| `ports/` | `llm`, `mcp_client`, `audit` (AuditEntry/AuditPort), `agent_provider`, `tool`, `sandbox`, `doc_intake` |
| `adapters/` | `anthropic` (LlmPort), `audit_postgres.PostgresAuditSink` (**ghi duy nhất** vào `audit_trail`), `mcp_client_stub`, `sandbox`, `registry` |

### modules
| Module | Trạng thái | Nội dung |
|--------|-----------|----------|
| `tenant` | ✅ | Tenant/Department/User models, auth routes, departments |
| `agent_builder` | ✅ | Agent/Tool/ApiIntegration models, KB (kb_models/kb_service/kb_retrieval), tool_service, routes |
| `orchestrator` | 🚧 Epic 3 (agent khác) | Story 3.1: `Workflow` model + CRUD; 3.2 runs/tasks đang làm |
| `mini_app` | ⛔ stub | Epic 4 |
| `actions` | ⛔ stub | Epic 5 |
| **`audit`** | 🟡 **read side mới** | `service.list_audit_entries` (read-only Trace query), `routes` `GET /audit`. Ghi vẫn chỉ qua `PostgresAuditSink` (AD-4) |

### Audit path (sau PR #1)
- **Write:** `AuditPort.log` → `PostgresAuditSink` (INSERT-only, RLS, crash-on-fail). Đường duy nhất.
- **Read (mới):** `audit.service.list_audit_entries` → `GET /audit` → Trace Dashboard. RLS tự scope tenant, KHÔNG filter tenant trong Python.
- Bảng `audit_trail`: `{id, tenant_id, run_id, step_id, agent_id, ts, type, input, output, latency_ms, model}` (append-only; GRANT SELECT+INSERT, REVOKE UPDATE/DELETE).

### scripts
| File | Vai trò |
|------|---------|
| `bootstrap_demo_tenant.py` | Seed demo tenant (idempotent): Tenant "SHB Demo" + 3 Dept + 3 User + gọi 2 module dưới |
| `demo_seed_agents.py` | 3 Agent + 1 KB doc + 1 Tool mỗi Agent |
| `demo_seed_workflow.py` | Hook: seed Workflow demo khi bảng `workflows` tồn tại, else defer |

Chạy: `cd backend && uv run python -m scripts.bootstrap_demo_tenant`

## Frontend (`frontend/src`)

| Thư mục | Nội dung |
|---------|---------|
| `routes/` | `login`, `dashboard`, `agents`, `agent-detail`, **`audit`** (Trace Dashboard mới). `/workflows /mini-apps /actions /settings` = `ComingSoon` (workflows do Epic 3 agent thay) |
| `components/ui/` | Primitives: Button, Card, Table, StatusPill, FormField, EmptyState, ErrorState, Skeleton, CodeBlock, ConfirmDialog, Toast, Tooltip |
| `components/agents/` | Agent Builder shell + tabs |
| `components/dashboard/` | KpiStrip, RecentRuns, EscalationInbox (hiện dùng mock) |
| **`components/audit/`** | **TraceTimeline, TraceEntryCard (mới)** |
| `components/CommandPalette/` | Cmd+K palette |
| `hooks/` | TanStack Query hooks (useAgents, useDepartments, …, **useAuditTrail** mới) |
| `lib/` | `api.ts` (apiFetch, unwrap envelope, JWT+tenant headers), `agentsApi`, …, **`auditApi` + `auditEntryMeta`** mới; `icons.tsx` (semantic icons + RunState locked) |

### Convention FE (bám theo)
- API: `apiFetch<T>` tự bơm JWT + `X-Tenant-Id`, unwrap `data`. Mỗi resource 1 file `lib/*Api.ts` + 1 hook `hooks/use*.ts`.
- Trạng thái: `StatusPill` chỉ nhận RunState locked (pending/running/success/error/escalated/draft) — map enum BE qua helper.
- Form controlled: KHÔNG dùng `FormField` cho controlled state (nó tự sở hữu onChange); dùng raw input + class `vaic-form-*` (xem IdentityTab).
- Icon: chỉ `semanticIcons` (lib/icons.tsx), stroke 1.5.

## Kiểm thử / build
- BE: `cd backend && uv run pytest` · `uv run ruff check`
- FE: `cd frontend && npm run build` (tsc --noEmit + vite) · `npm run test` (vitest)
