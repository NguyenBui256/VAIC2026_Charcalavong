# Project Roadmap — Trạng thái Epic (VAIC)

> Living doc. Cập nhật mỗi khi một lát cắt (slice) land. Nguồn kế hoạch gốc:
> `docs/superpowers/specs/2026-07-18-remaining-epics-roadmap-design.md`.
> Cập nhật gần nhất: 2026-07-18.

## Bảng trạng thái

| Epic | Nội dung | PRD | Trạng thái | Ghi chú |
|------|----------|-----|-----------|---------|
| 1 | Foundation & Contracts | §4.6 | ✅ DONE | auth, RLS×7, LlmPort, McpClientPort, AuditPort, PostgresAuditSink, model_catalog |
| 2 | Agent Builder | §4.1 | ✅ DONE | FR-1..6 |
| 3 | Workflow Orchestrator + HITL | §4.2 | 🚧 IN PROGRESS | **Agent khác.** 3.1 CRUD+UI ✅; 3.2 Run lifecycle đang chạy; 3.3/3.4 queued |
| 4 | Mini-App Builder | §4.3 | ⛔ DEFER | Stub; cần migration → tránh tranh migration-head khi Epic 3 đang land |
| 5 | Actions / Triggers | §4.4 | ⛔ DEFER | Stub; phụ thuộc Epic 4 |
| 6 | Trace Dashboard + Provenance | §4.5 | 🟡 PARTIAL | **FR-22 Timeline ✅ (lát cắt này).** FR-23 graph (SHOULD) + FR-24 export (DEFER) chưa làm |
| 7 | Integration & Demo Readiness | — | 🟡 PARTIAL | **Seed Agent+KB+Tool ✅ (lát cắt này).** Router wiring do Epic 3 agent; warm-run pre-provision chờ bảng runs |

## Rubric bar (SHB)

| Bar | Nguồn | Trạng thái |
|-----|-------|-----------|
| 1 — 2–3 specialist collab | Epic 3 dispatch ≥2 Agent (seed cung cấp 3 Agent) | ⏳ chờ Epic 3.4 |
| 2 — planner decompose | Epic 3.3 | ⏳ chờ Epic 3.3 |
| 3 — real tool use | Epic 3.4 gọi Tool (seed cung cấp Tool) | ⏳ chờ Epic 3.4 |
| 4 — trace dashboard | **Epic 6 Timeline `/audit`** | ✅ bề mặt sẵn sàng, sáng đủ khi Epic 3 Run chạy |

## Đã hoàn thành trong lát cắt này (PR #1 → rebuild)

### Epic 7-thin — Demo seed (độc lập Epic 3)
- `backend/scripts/bootstrap_demo_tenant.py` — thêm Dept Compliance, gọi 2 module dưới
- `backend/scripts/demo_seed_agents.py` — 3 Specialist Agent (Credit Analyst / Compliance Officer / Operations Verifier), mỗi Agent 1 KB doc (metadata, status=indexed) + 1 Tool (MCP-routed, schema hợp lệ)
- `backend/scripts/demo_seed_workflow.py` — hook phòng thủ: introspect `workflows`, auto-seed "Business Loan Pre-Screen" khi Epic 3.1 migration có, else deferral (không import model orchestrator)
- Idempotent find-or-create. Không tạo migration.

### Epic 6-thin — Trace Dashboard `/audit` (FR-22, độc lập Epic 3)
- BE `backend/app/modules/audit/service.py` — `list_audit_entries()` read-only, RLS-scoped, filter `run_id`/`type`, cap 500, order ts ASC (theo run) / DESC (global)
- BE `backend/app/modules/audit/routes.py` — `GET /audit?run_id=&type=&limit=`, envelope `{data,error,meta}`
- BE `backend/app/main.py` — include additive `audit_router`
- FE `frontend/src/routes/audit.tsx` — dashboard filter run_id (deep-link `/audit?run_id=`) + type
- FE `frontend/src/components/audit/{TraceTimeline,TraceEntryCard}.tsx` — timeline dọc, dot màu theo type, expand ra input/output JSON
- FE `frontend/src/lib/{auditApi,auditEntryMeta}.ts`, `hooks/useAuditTrail.ts`
- FE `frontend/src/App.tsx` — wire `/audit`

**Verify:** `tsc --noEmit` PASS · `npm run build` PASS · backend `py_compile` OK.

## Runway độc lập còn lại (không đụng Epic 3, không migration mới)
- 🟡 **FR-23 Collaboration graph** — graph view trên `/audit` (Orchestrator→Agents), SVG thuần. SHOULD.
- 🟡 **FR-24 Audit export** — export `audit_trail` JSON/CSV. DEFER (không ảnh hưởng demo).
- ❌ Dashboard real-wiring, run-view trace embed, Epic 4/5 — **phụ thuộc Epic 3** (runs endpoint) hoặc cần migration → chờ Epic 3 land thêm.

## Lưu ý điều phối
- 2 file dùng chung additive với Epic 3: `backend/app/main.py` + `frontend/src/App.tsx` (route/import cạnh nhau) → resolve nhẹ khi cả hai vào `rebuild`.
- Không auto-commit/push; PR #1 mở từ `feat/epic6-trace-epic7-seed` về `rebuild`.
