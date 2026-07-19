---
title: "Roadmap — Hoàn thành các Epic còn thiếu (VAIC)"
status: approved
created: 2026-07-18
branch: rebuild
strategy: demo-safe · gấp ≤3 ngày · song song có kiểm soát
covers_epics: [3, 4, 5, 6, 7]
supersedes: none
---

# Roadmap: Hoàn thành phần còn thiếu của VAIC

> Master roadmap sắp xếp 5 Epic còn lại (3,4,5,6,7). KHÔNG phải spec triển khai —
> mỗi Epic MUST có chu kỳ spec → plan → execute riêng. Đây là bản điều phối cấp cao
> để chốt ưu tiên, thứ tự, cắt scope, và luật chống xung đột khi chạy song song.

## 0. Bối cảnh & hiện trạng

Nền tảng VAIC (PRD `docs/prd.md`, 6 nhóm feature, FR-1..FR-28) chia thành 7 Epic.
Nguồn epic gốc: `_bmad-output/planning-artifacts/epics.md` (đã khôi phục từ commit `d8658bb^`).

| Epic | Nội dung | PRD | FRs | Trạng thái |
|------|----------|-----|-----|-----------|
| 1 | Foundation & Contracts | §4.6 | FR-25,26,27 + audit sink | ✅ DONE |
| 2 | Agent Builder | §4.1 | FR-1..6 | ✅ DONE |
| 3 | Workflow Orchestrator + HITL | §4.2 | FR-7..11 | ✅ DONE (thin-slice, backend) — head `135b295` |
| 4 | Mini-App Builder + Visibility | §4.3 | FR-12..17 | ❌ Stub — DEFER |
| 5 | Actions / Triggers | §4.4 | FR-18..20 | ❌ Stub — DEFER |
| 6 | Trace Dashboard + Provenance | §4.5 | FR-22,23,24 | ✅ DONE (merged, commit `63f009e`) — FR-22 Timeline, FR-23 Collaboration graph, FR-24 export |
| 7 | Integration & Demo Readiness | — | FR-28 + wiring | ✅ DONE (thin: bootstrap seed + worker entrypoint) — head `135b295` |

Bằng chứng code: `backend/app/modules/{orchestrator,mini_app,actions,audit}` đều stub 1 dòng,
chưa router, chưa migration. Frontend `/workflows /mini-apps /actions /audit` = `<ComingSoon>`.
Core infra (auth, RLS×7 migration, LlmPort, McpClientPort, AuditPort, model_catalog) REAL.

## 1. Chiến lược đã chốt

- **Ưu tiên:** Demo-safe — đảm bảo đủ **4 rubric bar SHB** sớm nhất; stretch cắt được.
- **Thời gian:** Gấp, ≤ 2–3 ngày → cắt scope mạnh, đánh dấu rõ MUST vs DEFER.
- **Thực thi:** Song song có kiểm soát — Epic 3/6/7-thin chạy đồng thời trên module tách bạch.

Rubric mapping:
- Bar 1 (2–3 specialist collab) ← Epic 3 dispatch tới ≥2 Agent (Epic 2).
- Bar 2 (planner decompose) ← Epic 3 decomposition (Story 3.3).
- Bar 3 (real tool use) ← Tool của Epic 2 được gọi trong Task execution (Story 3.4).
- Bar 4 (trace dashboard) ← Epic 6 Timeline view (FR-22) đọc `audit_trail`.

## 2. Cắt scope: MUST vs DEFER

| Hạng mục | Bar/SM | Quyết định | Lý do |
|----------|--------|-----------|-------|
| Epic 3 Orchestrator (thin slice) | Bar 1,2,3 | ✅ MUST | Lõi rubric |
| Epic 6 Trace — Timeline (FR-22) | Bar 4 | ✅ MUST | Bar 4 bắt buộc |
| Epic 7 — bootstrap tối thiểu (FR-28 thin) | Điều kiện demo | ✅ MUST | Không seed → không demo được |
| Epic 6 — Collaboration graph (FR-23) | — | 🟡 SHOULD | Timeline đã đủ bar 4 |
| Epic 3.6 — HITL escalation (FR-10) | — | 🟡 SHOULD | Maker-checker đẹp, không phải bar cứng |
| Epic 6 — Audit export (FR-24) | — | ⛔ DEFER | Không ảnh hưởng demo |
| Epic 4 — Mini-App Builder (FR-12..17) | SM-5 | ⛔ DEFER | Stretch, chỉ làm nếu vượt tiến độ |
| Epic 5 — Actions/Triggers (FR-18..20) | SM-6 | ⛔ DEFER | Phụ thuộc Epic 4 |

### Thin-slice Epic 3 (MUST)
Thứ tự: 3.1 Workflow CRUD → 3.2 Run lifecycle (CAS state machine + arq worker + tenant
bootstrap) → 3.3 Decompose (LLM→Tasks, Task Schema PRD §A1) → 3.4 Dispatch+claim+aggregate
(execute Agent qua LlmPort+Tools+KB) → 3.7 Runs list (tối giản) → 3.8 Live Run view (tối giản).

**Trim:** 3.5 feedback chỉ giữ field `confidence: float` (không logic tiêu thụ phức tạp);
3.6 HITL để sẵn hook (cột `awaiting_human` trong enum + route stub), chỉ hoàn thiện nếu dư giờ.

### Thin-slice Epic 6 (MUST)
- Đảm bảo Epic 3 Run-steps audit bằng `run_id/step_id` THẬT (bỏ stopgap `crud_audit_ids`).
- FR-22 Timeline view: `/audit` hoặc `/workflows/$id/runs/$runId` render Audit Trail dạng
  timeline card (type, agent, latency, expand-for-detail). Đây là màn hình chấm bar 4.

### Thin-slice Epic 7 (MUST)
- Script bootstrap seed: 1 Tenant (SHB Demo Bank), 3 Department (Credit/Compliance/Ops),
  3 Agent kèm KB+Tool, 1 Workflow ("Business Loan Pre-Screen"). Idempotent-lite.
- Wire router orchestrator vào `main.py` (additive).
- (SHOULD) pre-provision 1 warm Run cho cold-start an toàn (R-5).

## 3. Sequencing 3 ngày + 3 luồng song song

```
NGÀY 1
  Luồng A (BE core) : Epic 3.1 + 3.2        ← HARD GATE; land migration orchestrator đầu tiên
  Luồng B (FE)      : scaffold Trace-timeline + Workflow/Run UI shell (mock types, không chờ BE)
NGÀY 2
  Luồng A (BE core) : Epic 3.3 + 3.4        ← EXTEND AgentProviderPort.execute_task (mấu chốt)
  Luồng B (FE)      : nối Trace + Run list/live view vào endpoint thật
  Luồng C (demo)    : script bootstrap seed (phụ thuộc model Workflow từ 3.1)
NGÀY 3
  Integration       : chạy trọn 1 Workflow Run e2e → verify 4 bar trên Trace Dashboard
  Buffer/polish     : nếu vượt tiến độ → 3.6 HITL, hoặc FR-23 graph, hoặc khởi động Epic 4
```

Đường găng (critical path): 3.1 → 3.2 → 3.4 (cần AgentProviderPort.execute_task) → integration.
Luồng B & C không được chặn đường găng — luôn có mock/types để chạy trước.

## 4. Luật điều phối song song (chống xung đột)

- **Migration (rủi ro #1):** alembic chỉ 1 head. **Chỉ Luồng A tạo migration orchestrator.**
  Mọi luồng chạy `alembic heads` NGAY TRƯỚC khi viết revision; KHÔNG hardcode `down_revision`.
- **File ownership tách bạch:**
  - A → `backend/app/modules/orchestrator/*` + migration mới.
  - B → `frontend/src/routes|pages|components/*`.
  - C → `scripts/bootstrap*`.
  - Chung duy nhất: `backend/app/main.py` (thêm 1 dòng router-include, additive, rebase nếu chạm).
- **Port mấu chốt (quyết định NGÀY 1):** `AgentProviderPort` hiện chỉ `retrieve()`. Story 3.4
  cần `execute_task(agent_id, task_payload, *, tenant_id, department_id) -> TaskResult` chạy
  system prompt + model (LlmPort) + Tools (McpClientPort) + KB (retrieve) của Agent. Chọn 1:
  (a) extend AgentProviderPort, hoặc (b) orchestrator.service đọc config Agent qua public
  service của agent_builder (AD-1, không chạm models). **Khuyến nghị (a).**
- **Audit graduation:** Run-steps của Epic 3 phải dùng `run_id/step_id` thật → nguồn dữ liệu
  Trace bar 4. `audit.log()` là đường duy nhất tới `audit_trail` (AD-4), fail thì crash Run.
- **State machine (AD-6):** mọi transition `workflow_runs.status` & `tasks.status` dùng
  compare-and-set `UPDATE...WHERE id=? AND status=?`, check `rowcount==1`, `==0` → abandon.
- **Tenant qua arq (AD-10):** materialize `tenant_id` vào job kwargs; worker set
  `tenant_context` + `SET LOCAL app.tenant_id` ở statement đầu tiên.
- **Vận hành:** bash luôn qua subagent; KHÔNG auto-commit/push (chỉ commit local khi được đồng ý).

## 5. Rủi ro & giảm thiểu

| # | Risk | Mitigation |
|---|------|-----------|
| R1 | AgentProviderPort thiếu năng lực dispatch | Chốt `execute_task` ngày 1, trước khi vào 3.4 |
| R2 | LLM decompose bất định lúc demo live | Cap max-task; temperature thấp; rehearse warm run; escalate nếu vượt ceiling |
| R3 | Migration head lệch giữa các luồng | Chỉ A sở hữu migration orchestrator; re-check `heads` mỗi lần |
| R4 | Trắng demo do integration trễ | Ngày 3 = buffer; bootstrap pre-provision 1 warm Run |
| R5 | Trace render chậm/ thiếu step | Log đủ mọi step; test trên Run ~100 entry trước demo |

## 6. Definition of Done (roadmap-level)

- [x] Epic 3 thin-slice: định nghĩa Workflow → Run → decompose → dispatch ≥2 Agent →
      tool call thật → aggregate, tất cả audit bằng run_id/step_id thật. — DONE, head `135b295`.
- [x] Epic 6: Timeline view render Audit Trail của 1 Run e2e, đủ 4 bar quan sát được. — DONE, merged commit `63f009e` (FR-22 Timeline, FR-23 Collaboration graph, FR-24 export). Task 8 (FE run-views) phần lớn đã được Trace Dashboard `/audit?run_id=` phủ (deep-link theo Run); riêng embed trace trực tiếp trong `/workflows/$id/runs/$runId` vẫn DEFER nếu cần.
- [x] Epic 7-thin: bootstrap seed chạy < 60s, ra 3 Agent + 1 Workflow demo-ready. — DONE (`backend/scripts/bootstrap_demo_tenant.py` + `bootstrap_demo_agents_workflow.py`).
- [x] 1 lần chạy e2e demo-safe được rehearse thành công (warm) — DONE nhưng với STUB LLM (`backend/tests/integration/test_demo_smoke.py`); real live run cần Anthropic API key thật (PRD OQ-2), chưa rehearse.
- [ ] DEFER items (Epic 4, 5, FR-23/24, 3.6) ghi rõ là hoãn, có hook không nợ kỹ thuật chặn. — vẫn DEFER, chưa mở.

### Cập nhật trạng thái (2026-07-18, sau khi Epic 3 + 7-thin hoàn thành)

- Epic 3 (backend thin-slice) và Epic 7-thin (bootstrap) đã DONE, tất cả commit local trên
  branch `rebuild`, branch head `135b295`, KHÔNG push. Chi tiết task-by-task: `.superpowers/sdd/progress.md`.
- Bars 1–3 (specialist collab, planner decompose, real tool use) đã chứng minh e2e qua smoke test.
- Bar 4 (Trace Dashboard) — DONE, merged `63f009e` 2026-07-18. Tất cả 4 rubric bar SHB nay đã phủ end-to-end.
- Known pre-existing, không phải do Epic 3/7 gây ra: `test_arq_tenant_context.py` có smell cô lập test
  giữa các file (baseline 350 pass / 1 flaky / 8 lỗi khi chạy full `pytest tests/`; chạy từng file riêng thì sạch).

## 7. Bước tiếp theo (per-Epic cycle)

Mỗi Epic MUST → spec → plan → execute riêng:
1. **Epic 3** — plan đã có (`plans/260718-0052-epic-3-orchestrator/`): mở rộng brief 3.3–3.8
   thành artifact đầy đủ; chốt quyết định `execute_task`. → execute trước tiên (đường găng).
2. **Epic 6 (thin)** — viết spec Timeline view + audit-graduation. Có thể scaffold FE song song.
3. **Epic 7 (thin)** — viết spec bootstrap seed + router wiring. Sau khi 3.1 có model Workflow.

DEFER (chỉ mở khi vượt tiến độ): Epic 4 Mini-App → Epic 5 Actions → FR-23 graph / FR-24 export / 3.6 HITL.

## 8. Câu hỏi chưa giải quyết

1. Quyết định `execute_task`: extend AgentProviderPort (a) hay orchestrator tự đọc config (b)? — khuyến nghị (a), cần chốt ngày 1.
2. Nhân lực thực tế cho 3 luồng song song: 1 người luân phiên hay nhiều session/agent đồng thời? — ảnh hưởng tính khả thi mốc 3 ngày.
3. Ceiling max-task cho decomposition (R2) — chốt con số cụ thể (gợi ý ≤ 5).
