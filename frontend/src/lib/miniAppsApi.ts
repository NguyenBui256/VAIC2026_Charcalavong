import { apiFetch } from "./api";

export interface MiniApp {
  id: string; name: string; slug: string; description: string;
  entity_schema: { fields: Array<{ name: string; type: string; label?: string; options?: string[]; required?: boolean }> };
  ui_spec: Record<string, unknown>;
  visibility_tier: "public" | "need_auth" | "private";
  whitelist_user_ids: string[]; build_status: "pending" | "building" | "ready" | "failed";
  build_error: string | null; created_at: string; updated_at: string;
}

export interface CreateMiniAppInput {
  name: string; description?: string; expected_output?: string;
  entity_schema?: MiniApp["entity_schema"]; visibility_tier?: string; whitelist_user_ids?: string[];
}

export const listMiniApps = () => apiFetch<MiniApp[]>("/mini-apps");
export const getMiniApp = (id: string) => apiFetch<MiniApp>(`/mini-apps/${id}`);
export const createMiniApp = (input: CreateMiniAppInput) =>
  apiFetch<MiniApp>("/mini-apps", { method: "POST", body: JSON.stringify(input) });
export const rebuildMiniApp = (id: string) =>
  apiFetch<{ app_id: string; build_status: string }>(`/mini-apps/${id}/rebuild`, { method: "POST" });
export const getScopedToken = (id: string) =>
  apiFetch<{ token: string }>(`/mini-apps/${id}/session-token`, { method: "POST" });
