# Auto-Loan Secured-Lending Demo — Design Spec

**Date:** 2026-07-19
**Status:** Approved (brainstorming) → ready for implementation plan
**Goal:** Demonstrate the end-to-end business flow of *Thẩm định & Giải ngân Vay Thế chấp Ô tô* (Secured Auto Loan) on the existing VAIC platform, driven **entirely by seeded database data + existing UI**, with **zero product-code changes**.

## Non-negotiable constraints

- **No product code changes.** No edits to backend modules, frontend components, or migrations. The ONLY new file is one idempotent seed script under `backend/scripts/`.
- **Everything via seed data + existing UI.** The workflow, agents, approval gates, customer form, event→workflow binding, admin views — all are seeded rows consumed by machinery that already exists and is wired.
- **Documents = metadata fields**, not binary uploads (platform has no file-upload field type). Each required document is represented as a boolean/enum "đã nộp" field (+ optional image-link longtext).
- **Customer = a seeded demo user** with `need_auth` access to the mini-app (platform has no anonymous/external row path). This was explicitly accepted during brainstorming.

## Platform facts established (verified in code)

| Capability | Status | Reference |
|---|---|---|
| Graph workflow engine (DAG of agent nodes) | EXISTS | `orchestrator/graph_engine.py`, `models.py:220-317` |
| Human-approval gate = node with ≥1 approver → run pauses `awaiting_human` / node `awaiting_approval`; resumes on decision | EXISTS | `graph_engine.py:292-301`; `graph_review.py:99-142`; worker resume `orchestrator_worker.py:130-142` |
| Seed a full graph as data (nodes+edges+approvers) | EXISTS | `graph_authoring.py:87 replace_workflow_graph(...)` |
| Each node binds one Specialist Agent (agent required per node) | EXISTS | `graph_engine.py:116-169`; validation requires agent |
| Mini-app row create → `ActionEvent` outbox → cron 5s → match `ActionBinding` → `orchestrator.create_run` → run workflow + notify | EXISTS, wired | `mini_app/service.py:36,169`; `action/emit.py:18`; `action/worker.py:32,60`; `action/service.py:128-207` |
| Event matches binding on **`database_id` + `event_type`** (NOT NULL) | EXISTS | `action/service.py:155-167`; `action/models.py:40-42` |
| Approval UI: Approve/Retry/Override/Reject, gated to the node's approver | EXISTS | `frontend/.../runs/RunReviewPanel.tsx:153-215`; `lib/runsApi.ts:131-140` |
| Admin rows viewer (read-only) for a database's rows | EXISTS | route `database.tsx` → `MiniAppDatabaseSection` → `DatabaseRowsCard`; `database_routes.py:105`; `database_service.py:80` |
| Mini-app must be **built** (esbuild worker) to render | EXISTS | `mini_app_worker.py:86-153` (`build_mini_app`) |

**Key linchpin:** because binding matches on `database_id`, the customer mini-app **must be created from a `mini_app_databases` template** (the LLM-description-only create path produces `database_id = NULL` and would be `skipped`, `action/service.py:155-156`). The form **schema** is authored by the LLM (`emission.emit_schema`) but persisted as a database template so events can fire.

## Architecture / data flow

```
Customer (demo user) fills mini-app form ─▶ POST /apps/{id}/rows (row.created)
  └▶ mini_app._emit_row_change ─▶ action_events(pending, database_id set)
       └▶ cron dispatch_action_events_fanout (5s) ─▶ process_tenant_action_events
            └▶ dispatch_pending_events: match ActionBinding(database_id,row.created)
                 ├▶ orchestrator.create_run(workflow, input={data,row_id,...})
                 └▶ create_notification(action.dispatched) → approvers
                      └▶ worker run_workflow ─▶ graph_orchestrate
                           n1 ─▶ (n2 ‖ n3) ─▶ n4 [PAUSE awaiting_human]
                             admin(Trưởng phòng TĐ) Approve @ RunReviewPanel ─▶ resume
                           ─▶ n5 ─▶ n6 [PAUSE awaiting_human]
                             admin(Vận hành) Approve ─▶ resume ─▶ completed
```

## Seed contents (the one script: `bootstrap_auto_loan_demo.py`)

Idempotent, targets tenant **"SHB Demo"** (reuse `bootstrap_demo_tenant.py` foundation; create if absent). Uses existing services, not raw SQL, wherever a service exists.

### 1. Users / approvers (in SHB Demo tenant)
- `khachhang@shb.demo` — role Customer; fills the form (`need_auth`, same department as the app).
- `truongphong.td@shb.demo` — Credit dept manager; **approver of node 4**.
- `vanhanh@shb.demo` — Back-Office/Ops; **approver of node 6**.
- Reuse existing demo users if already seeded; only fill gaps. Capture their UUIDs for approver + notify wiring.

### 2. Six Specialist Agents (`agent_builder.create_agent`)
Each has a Vietnamese system prompt stating its role, inputs, and a compact structured output. Model = demo default (see Open Question 1).

| key | Agent | Output (summary) |
|---|---|---|
| rm_intake | RM Intake Agent | Kiểm tra đủ/thiếu giấy tờ B1 từ dữ liệu row; liệt kê thiếu sót |
| credit_appraisal | Credit Appraisal (CIC/DTI) | Ước tính DTI, đề xuất hạn mức/lãi suất/thời hạn (tờ trình tín dụng) |
| collateral_valuation | Collateral Valuation | Định giá xe, tỷ lệ cho vay tối đa (LTV 70–80%) |
| credit_memo | Credit Memo Agent | Tổng hợp tờ trình + định giá thành đề xuất phê duyệt |
| back_office | Back Office Agent | Danh mục HĐ/giấy tờ cần ký & hoàn thiện TSĐB (B5) |
| disbursement | Disbursement Agent | Soạn lệnh chuyển tiền/UNC + checklist đăng ký GDBĐ (B6) |

### 3. Workflow + graph (`orchestrator.create_workflow` then `replace_workflow_graph`)
- Workflow name: **"Thẩm định & Giải ngân Vay Thế chấp Ô tô"**.
- Nodes n1..n6 mapped to agents above; hand-laid positions (n2/n3 side-by-side).
- Edges: `n1→n2, n1→n3, n2→n4, n3→n4, n4→n5, n5→n6`.
- `approver_user_ids`: **n4 = [truongphong.td]**, **n6 = [vanhanh]**; all others empty (auto).

### 4. Database template (`mini_app_databases`)
- Name: **"Hồ sơ vay thế chấp ô tô"**.
- `entity_schema` authored by LLM: `emission.emit_schema(description_vi, expected_output_vi)`; persist the returned schema as the template. Fields (all scalar):
  - Người vay: `ho_ten` (string), `cccd` (string), `sdt` (string), `tinh_trang_hon_nhan` (enum: Độc thân/Đã kết hôn), `thu_nhap_thang` (number).
  - Xe/khoản vay: `loai_xe` (enum: Xe mới/Xe cũ), `hang_dong_xe` (string), `gia_xe` (number), `so_tien_vay_de_nghi` (number).
  - Checklist giấy tờ B1 (boolean "đã nộp"): `gt_cccd`, `gt_hon_nhan`, `gt_hdld`, `gt_sao_ke_luong`, `gt_hd_mua_ban_xe`, `gt_phieu_coc`, `gt_hoa_don_gia`, `gt_ca_vet_cu` (enum n/a cho xe mới).
  - `link_ho_so` (longtext) — dán link ảnh/scan.
- If LLM unavailable, fall back to a hand-written schema literal of the same shape (script constant), so seeding never blocks.

### 5. Mini-app instance (bound to the database)
- Create the app **from `database_id`** (schema-copy path, no LLM at create time) so `mini_apps.database_id` is set → events carry `database_id`.
- `visibility_tier = need_auth`; enqueue `build_mini_app` so it renders.

### 6. ActionBinding (`action` module — seed row)
- `database_id` = the template above, `event_type = "row.created"`, `workflow_id` = the workflow, `notify_user_ids = [truongphong.td, vanhanh]`, `is_active = true`.
- Respect NOT-NULL FKs + unique `(tenant_id, name)`.

## The three UIs (all existing screens — no new code)
- **Customer form:** login `khachhang` → open mini-app "Hồ sơ vay thế chấp ô tô" → fill → submit.
- **Hồ sơ management:** route `database` → the template's rows table (all submissions, read-only).
- **Processing status + approval:** Workflow Runs / `RunTrackingView` (live node states, `awaiting_human`) + `RunReviewPanel` (Approve/Reject/Rollback) + Audit/Trace deep-link.

## Demo runbook (operator steps, no code)
1. Infra up; run backend (8000), **worker** (`uv run python -m scripts.run_worker`), frontend (5173).
2. Run `bootstrap_auto_loan_demo.py` (idempotent).
3. Login `khachhang` → mini-app → fill sample hồ sơ → Submit.
4. Within ~5s: run auto-created; approvers get "New submission" notification.
5. Watch run: n1 → n2‖n3 (parallel) → **n4 pauses** (run `awaiting_human`).
6. Login `truongphong.td` → open run → n4 → **Approve** → resumes → n5 → **n6 pauses**.
7. Login `vanhanh` → **Approve** n6 → run **completed** (giải ngân).
8. Show `database` rows viewer + Audit trace for the full story.

## Out of scope (explicit)
- Real anonymous/external customer portal; binary file upload; human-approval push notification wiring (approver sees run/notification but no dedicated approval push — generic `action.dispatched` notification only).

## Open questions
1. **LLM key**: if `backend/.env` has no live model key, agents run the stub adapter (canned output) — flow/pause/approve still real. Acceptable for the demo, or must agents produce live LLM output?
2. **Live builder showcase**: seed the mini-app instance for determinism (recommended). Optionally also demonstrate creating a mini-app live via the builder chat — but that path yields `database_id = NULL` and will NOT trigger the workflow, so it is showcase-only, not the wired instance. Include this optional step in the runbook or omit?
3. **Approver identity for override/notification**: confirm the two approver users are acceptable role names, or map to existing seeded demo users instead of new ones.
