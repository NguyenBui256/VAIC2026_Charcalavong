# Shared Pool (Tools/Integrations/KB) — Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FE bám theo backend shared-pool: trang top-level Tools + Knowledge Base (quản lý pool, chỉ `builder`); tab Agent Builder Tools/KB đổi thành bộ chọn grant; Integrations lên tenant-level; bỏ authoring per-agent.

**Architecture:** React 19 + TS + TanStack Query + react-router. Tách API thành pool CRUD (`/tools`,`/integrations`,`/kb/documents`) vs agent grant (`/agents/{id}/tools`,`/agents/{id}/kb-documents`). Role gate qua `useAuth().user.role === "builder"`.

**Tech Stack:** Vite, React 19, TypeScript, TanStack Query, react-router, vitest.

## Global Constraints

- API base + envelope: dùng `apiFetch` (`src/lib/api.ts`) — tự gắn JWT + tenant headers, unwrap `{data}`.
- Role gate: chỉ hiện nút create/update/delete pool khi `role === "builder"`. Member vẫn xem pool + grant vào agent mình.
- Endpoint BE (từ Plan 1 / Task 7): pool `GET/POST /tools`, `PATCH/DELETE /tools/{id}`, `POST /tools/{id}/test`; `GET/POST /integrations`, `PATCH/DELETE /integrations/{id}`; `GET/POST /kb/documents`, `DELETE /kb/documents/{id}`. Grant: `GET/POST /agents/{id}/tools` + `DELETE /agents/{id}/tools/{toolId}`; `GET/POST /agents/{id}/kb-documents` + `DELETE /agents/{id}/kb-documents/{docId}`. (Xác nhận path grant KB thật = `/agents/{id}/kb-documents` khi implement — Task 7 report nêu vậy.)
- File > 200 dòng cân nhắc tách (component con). Kebab/descriptive naming.
- **User override:** test OPTIONAL; không tự chạy lint/build/test khi user chưa yêu cầu — trừ verify tối thiểu nêu trong task. Commit LOCAL, không push.
- Chạy FE trong `frontend/`: `npm run build` chỉ khi task yêu cầu verify.

---

## File Structure

- `src/lib/integrationsApi.ts` — MODIFY: bỏ `agentId`, path `/integrations`, type bỏ `agent_id`.
- `src/lib/toolsApi.ts` — MODIFY/SPLIT: pool CRUD `/tools` + test; giữ type `Tool` (+`kind`,`integration_id`).
- `src/lib/agentGrantsApi.ts` — CREATE: grant tools + kb (`/agents/{id}/tools`, `/agents/{id}/kb-documents` list/attach/detach).
- `src/lib/kbApi.ts` — MODIFY: pool `/kb/documents` (list/upload/delete).
- `src/hooks/useIntegrations.ts`,`useIntegrationMutations.ts` — MODIFY: tenant-level (bỏ agentId).
- `src/hooks/useCatalogTools.ts` — CREATE: pool tools query + mutations.
- `src/hooks/useKbPool.ts` — CREATE: pool KB query + mutations.
- `src/hooks/useAgentGrants.ts` — CREATE: granted tools/kb per agent + attach/detach.
- `src/hooks/useIsBuilder.ts` — CREATE: role gate.
- `src/routes/tools/ToolsPage.tsx` — CREATE: trang pool Tools + Integrations (builder-gated).
- `src/routes/knowledge-base/KnowledgeBasePage.tsx` — CREATE: trang pool KB (builder-gated).
- `src/components/agents/tabs/ToolsTab.tsx`,`KnowledgeBaseTab.tsx` — MODIFY: grant-picker.
- `src/components/agents/tabRegistry.ts` — MODIFY: bỏ tab `api-integrations`; tools/kb = grant.
- `src/components/agents/useTabCounts.ts` — MODIFY: count = granted count.
- `src/App.tsx` — MODIFY: route `/tools`,`/knowledge-base` render trang mới (bỏ ComingSoon).
- Giữ & tái dùng: `ToolEditor.tsx`, `IntegrationEditor.tsx`, `IntegrationSelect.tsx`, `ToolTestPanel.tsx` (đổi sang pool-level props).
- Retire: `ApiIntegrationsTab.tsx` (bỏ khỏi registry; xoá file), `useAgentTools.ts` cũ (thay bằng useCatalogTools + useAgentGrants).

---

### Task 1: API — integrations tenant-level

**Files:** Modify `src/lib/integrationsApi.ts`

**Interfaces:**
- Produces: `listIntegrations(): Promise<ApiIntegration[]>`, `createIntegration(input)`, `updateIntegration(id, patch)`, `deleteIntegration(id)`, `testIntegration(id)`. `ApiIntegration` bỏ `agent_id`.

- [ ] **Step 1: rewrite** — bỏ mọi tham số `agentId`, đổi path `/agents/${agentId}/integrations` → `/integrations`:
```typescript
export interface ApiIntegration {
  id: string; name: string; base_url: string; auth_header_masked: string;
  schema: Record<string, unknown> | null; last_used_at: string | null;
  created_at: string; updated_at: string;
}
export function listIntegrations(): Promise<ApiIntegration[]> {
  return apiFetch<ApiIntegration[]>(`/integrations`);
}
export function createIntegration(input: CreateIntegrationInput): Promise<ApiIntegration> {
  return apiFetch(`/integrations`, { method: "POST", body: JSON.stringify(input) });
}
export function updateIntegration(id: string, patch: UpdateIntegrationInput): Promise<ApiIntegration> {
  return apiFetch(`/integrations/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
}
export function deleteIntegration(id: string): Promise<{ id: string }> {
  return apiFetch(`/integrations/${id}`, { method: "DELETE" });
}
export function testIntegration(id: string): Promise<IntegrationTestResult> {
  return apiFetch(`/integrations/${id}/test`, { method: "POST" });
}
```
(Giữ `CreateIntegrationInput`/`UpdateIntegrationInput`/`IntegrationTestResult`.)

- [ ] **Step 2: commit (local)** — `git commit -m "feat(fe): tenant-level integrations api"`

---

### Task 2: API — pool tools + grant api

**Files:** Modify `src/lib/toolsApi.ts`; Create `src/lib/agentGrantsApi.ts`

**Interfaces:**
- Produces (toolsApi): `listCatalogTools()`, `createTool(input)`, `updateTool(id, patch)`, `deleteTool(id)`, `testTool(id, sampleInput)`. `Tool` giữ `kind`,`integration_id`.
- Produces (agentGrantsApi): `listAgentTools(agentId)`, `attachAgentTool(agentId, toolId)`, `detachAgentTool(agentId, toolId)`, `listAgentKb(agentId)`, `attachAgentKb(agentId, docId)`, `detachAgentKb(agentId, docId)`.

- [ ] **Step 1: toolsApi pool CRUD** — đổi path bỏ agentId:
```typescript
export function listCatalogTools(): Promise<Tool[]> { return apiFetch(`/tools`); }
export function createTool(input: CreateToolInput): Promise<Tool> {
  return apiFetch(`/tools`, { method: "POST", body: JSON.stringify(input) }); }
export function updateTool(id: string, patch: UpdateToolInput): Promise<Tool> {
  return apiFetch(`/tools/${id}`, { method: "PATCH", body: JSON.stringify(patch) }); }
export function deleteTool(id: string): Promise<{ id: string }> {
  return apiFetch(`/tools/${id}`, { method: "DELETE" }); }
export function testTool(id: string, sampleInput: Record<string, unknown>): Promise<ToolTestResult> {
  return apiFetch(`/tools/${id}/test`, { method: "POST", body: JSON.stringify({ sample_input: sampleInput }) }); }
```
`CreateToolInput` = `{ display_name; description; params_schema; output_schema; integration_id }` (khớp BE create_catalog_tool). Bỏ field `agent_id` khỏi `Tool` nếu có.

- [ ] **Step 2: agentGrantsApi**
```typescript
// src/lib/agentGrantsApi.ts — attach/detach shared pool resources onto an agent.
import { apiFetch } from "./api";
import type { Tool } from "./toolsApi";
import type { KbDocument } from "./kbApi";

export function listAgentTools(agentId: string): Promise<Tool[]> {
  return apiFetch(`/agents/${agentId}/tools`); }
export function attachAgentTool(agentId: string, toolId: string): Promise<unknown> {
  return apiFetch(`/agents/${agentId}/tools`, { method: "POST", body: JSON.stringify({ tool_id: toolId }) }); }
export function detachAgentTool(agentId: string, toolId: string): Promise<unknown> {
  return apiFetch(`/agents/${agentId}/tools/${toolId}`, { method: "DELETE" }); }
export function listAgentKb(agentId: string): Promise<KbDocument[]> {
  return apiFetch(`/agents/${agentId}/kb-documents`); }
export function attachAgentKb(agentId: string, docId: string): Promise<unknown> {
  return apiFetch(`/agents/${agentId}/kb-documents`, { method: "POST", body: JSON.stringify({ document_id: docId }) }); }
export function detachAgentKb(agentId: string, docId: string): Promise<unknown> {
  return apiFetch(`/agents/${agentId}/kb-documents/${docId}`, { method: "DELETE" }); }
```
(Xác nhận body key `tool_id`/`document_id` + path khớp BE routes khi implement.)

- [ ] **Step 3: commit (local)** — `git commit -m "feat(fe): pool tools api + agent grant api"`

---

### Task 3: API — pool KB

**Files:** Modify `src/lib/kbApi.ts`

**Interfaces:**
- Produces: `listKbDocuments()`, `uploadKbDocument(file)`, `deleteKbDocument(id)`. `KbDocument` bỏ `agent_id`.

- [ ] **Step 1: rewrite path** bỏ agentId → `/kb/documents`:
```typescript
export function listKbDocuments(): Promise<KbDocument[]> { return apiFetch(`/kb/documents`); }
export function uploadKbDocument(file: File): Promise<KbDocument> {
  const fd = new FormData(); fd.append("file", file);
  return apiFetch(`/kb/documents`, { method: "POST", body: fd }); }
export function deleteKbDocument(id: string): Promise<{ id: string }> {
  return apiFetch(`/kb/documents/${id}`, { method: "DELETE" }); }
```
(Giữ hằng số validate `KB_MAX_BYTES`/extensions/mime.)

- [ ] **Step 2: commit (local)** — `git commit -m "feat(fe): pool kb api"`

---

### Task 4: Hooks — pool + grant + integrations tenant-level

**Files:** Modify `src/hooks/useIntegrations.ts`,`useIntegrationMutations.ts`; Create `useCatalogTools.ts`,`useKbPool.ts`,`useAgentGrants.ts`

**Interfaces:**
- Produces: `useIntegrations()`, `useIntegrationMutations()`; `useCatalogTools()` + `useCatalogToolMutations()`; `useKbPool()` + `useKbPoolMutations()`; `useAgentGrants(agentId)` (tools+kb granted + attach/detach mutations).

- [ ] **Step 1: useIntegrations tenant** — queryKey `["integrations"]`, `queryFn: listIntegrations` (bỏ agentId). `useIntegrationMutations` mutationFn dùng api mới (no agentId), invalidate `["integrations"]`.
- [ ] **Step 2: useCatalogTools** — queryKey `["catalog-tools"]`, `queryFn: listCatalogTools`; mutations create/update/remove/test → invalidate `["catalog-tools"]`.
- [ ] **Step 3: useKbPool** — queryKey `["kb-pool"]`, `queryFn: listKbDocuments`; poll 2s khi có doc `status==="processing"` (giữ pattern useKbDocuments cũ); mutations upload/remove.
- [ ] **Step 4: useAgentGrants(agentId)** — queries `["agent-tools", agentId]` (`listAgentTools`) + `["agent-kb", agentId]` (`listAgentKb`); mutations attach/detach tool+kb → invalidate tương ứng.
- [ ] **Step 5: commit (local)** — `git commit -m "feat(fe): pool + grant query hooks"`

---

### Task 5: Role gate hook

**Files:** Create `src/hooks/useIsBuilder.ts`

**Interfaces:**
- Consumes: `useAuth()` (`src/hooks/useAuth.ts`) — `user.role`.
- Produces: `useIsBuilder(): boolean`.

- [ ] **Step 1: implement**
```typescript
// src/hooks/useIsBuilder.ts — pool management is builder-only (spec §5).
import { useAuth } from "./useAuth";
export function useIsBuilder(): boolean {
  const { user } = useAuth();
  return user?.role === "builder";
}
```
- [ ] **Step 2: commit (local)** — `git commit -m "feat(fe): useIsBuilder role gate"`

---

### Task 6: Top-level Tools page (pool tools + integrations)

**Files:** Create `src/routes/tools/ToolsPage.tsx` (+ tách con nếu >200 dòng: `ToolsSection.tsx`,`IntegrationsSection.tsx`)

**Interfaces:**
- Consumes: `useCatalogTools`,`useCatalogToolMutations`,`useIntegrations`,`useIntegrationMutations`,`useIsBuilder`; tái dùng `ToolEditor`,`IntegrationEditor`,`ToolTestPanel`,`IntegrationSelect`.
- Produces: `<ToolsPage />` (default export) cho route `/tools`.

- [ ] **Step 1: layout** — 2 section: "Integrations" (list từ `useIntegrations`, mỗi item name+base_url+masked auth; nút Test/Edit/Delete) và "Tools" (list `useCatalogTools`, mỗi item display_name + kind badge + integration link; nút Edit/Delete/Test). `useIsBuilder()` gate: ẩn nút New/Edit/Delete khi không phải builder (chỉ xem). `ToolEditor`/`IntegrationEditor` mở modal/inline, gọi mutations pool (không agentId). `IntegrationSelect` populate từ pool.
- [ ] **Step 2: reuse editors** — sửa `ToolEditor`/`IntegrationEditor`/`IntegrationSelect` props: bỏ `agentId`, nhận mutations pool. `ToolEditor` field: display_name, description, IntegrationSelect (integration_id), params_schema/output_schema JSON. (Bỏ embedded_python nếu BE không dùng — kind=integration.)
- [ ] **Step 3 (OPTIONAL verify):** `npm run build` không lỗi type.
- [ ] **Step 4: commit (local)** — `git commit -m "feat(fe): shared Tools + Integrations management page"`

---

### Task 7: Top-level Knowledge Base page (pool)

**Files:** Create `src/routes/knowledge-base/KnowledgeBasePage.tsx`

**Interfaces:**
- Consumes: `useKbPool`,`useKbPoolMutations`,`useIsBuilder`.
- Produces: `<KnowledgeBasePage />` cho route `/knowledge-base`.

- [ ] **Step 1: layout** — list docs pool (filename, status pill, chunk_count, size); builder: nút Upload (file input) + Delete; member: chỉ xem. Poll status qua useKbPool. Tái dùng UI pattern từ `KnowledgeBaseTab` cũ nhưng nguồn = pool (no agentId).
- [ ] **Step 2 (OPTIONAL verify):** `npm run build`.
- [ ] **Step 3: commit (local)** — `git commit -m "feat(fe): shared Knowledge Base management page"`

---

### Task 8: Agent Builder tabs → grant pickers + registry

**Files:** Modify `src/components/agents/tabs/ToolsTab.tsx`,`KnowledgeBaseTab.tsx`,`tabRegistry.ts`,`useTabCounts.ts`; Delete `tabs/ApiIntegrationsTab.tsx`

**Interfaces:**
- Consumes: `useCatalogTools`/`useKbPool` (pool list) + `useAgentGrants(agentId)` (granted + attach/detach) + `useIsBuilder` (chỉ builder mới grant — theo spec, grant = builder + owns/same-dept; FE gate builder, BE authoritative).

- [ ] **Step 1: ToolsTab grant-picker** — hiển thị pool tools (`useCatalogTools`), mỗi dòng checkbox = đã-grant (`useAgentGrants(agentId).tools`); toggle → attach/detach. Bỏ New/Edit/Delete (authoring chuyển sang trang Tools). Link "Manage tools" → `/tools`.
- [ ] **Step 2: KnowledgeBaseTab grant-picker** — tương tự với pool KB + `useAgentGrants.kb`.
- [ ] **Step 3: tabRegistry** — bỏ entry `api-integrations` (integrations không còn per-agent). Giữ knowledge-base, tools (grant), identity, prompt, model. Cập nhật `countKey` nếu cần.
- [ ] **Step 4: useTabCounts** — count = số đã-grant (từ useAgentGrants), không phải pool.
- [ ] **Step 5: xoá** `ApiIntegrationsTab.tsx` + import của nó (grep). Xoá `useAgentTools.ts` cũ nếu không còn caller (grep).
- [ ] **Step 6 (OPTIONAL verify):** `npm run build`.
- [ ] **Step 7: commit (local)** — `git commit -m "feat(fe): agent tabs as grant pickers, drop per-agent integrations tab"`

---

### Task 9: Routes + nav wiring

**Files:** Modify `src/App.tsx`; (optional) `src/components/Sidebar.tsx`,`CommandPalette/navigationCommands.ts`

**Interfaces:**
- Consumes: `ToolsPage`,`KnowledgeBasePage`.

- [ ] **Step 1: App.tsx** — thay `<ComingSoon title="Tools"/>` (`/tools`) bằng `<ToolsPage/>`; `<ComingSoon title="Knowledge Base"/>` (`/knowledge-base`) bằng `<KnowledgeBasePage/>`. Import lazy như route khác.
- [ ] **Step 2 (optional):** Sidebar/CommandPalette — giữ 2 entry hiện có; (không thêm Integrations riêng — gộp trong Tools page). Không bắt buộc.
- [ ] **Step 3: VERIFY** — `npm run build` PASS (type-check + bundle). Sửa lỗi type do đổi API tới khi sạch.
- [ ] **Step 4: commit (local)** — `git commit -m "feat(fe): wire shared Tools + KB pages into routes"`

---

## Self-Review

**Spec coverage (§6):**
- Trang Tools chung (tools+integrations, builder-gated): Task 6 + role gate Task 5. ✔
- Trang KB chung (builder-gated): Task 7. ✔
- Agent tabs → grant picker: Task 8. ✔
- Bỏ authoring per-agent + api-integrations tab: Task 8 (xoá tab) + Task 6 (editor chuyển pool). ✔
- API split pool vs grant: Task 1-3. ✔
- Role gate builder: Task 5, dùng Task 6/7/8. ✔
- Route wiring: Task 9. ✔

**Placeholder scan:** code cụ thể cho api/hooks/role-gate; page/tab mô tả composition + tái dùng component có sẵn (props nêu rõ). Không TBD.

**Type consistency:** `Tool`/`ApiIntegration`/`KbDocument` bỏ agent_id nhất quán (Task 1-3). `useAgentGrants(agentId)` trả `{tools, kb, attach*, detach*}` dùng ở Task 8. `useIsBuilder()` boolean dùng Task 6/7/8.

## Unresolved questions

1. Path grant KB thật: `/agents/{id}/kb-documents` (Task 7 report) — xác nhận khi implement (nếu BE dùng `/agents/{id}/kb/documents` thì đổi agentGrantsApi + hook).
2. Body key attach: `{tool_id}` / `{document_id}` — khớp BE route handler (xác nhận).
3. `ToolEditor` field `embedded_python`/`header.auth` cũ: kind=integration không cần → gỡ khỏi form pool (xác nhận CreateToolInput BE chỉ nhận display_name/description/params_schema/output_schema/integration_id).
4. Member (non-builder) có được grant tool/kb vào agent mình không? BE: grant = builder + owns/same-dept. Nếu member không builder thì grant-picker read-only cho họ — FE gate theo builder; BE authoritative.
