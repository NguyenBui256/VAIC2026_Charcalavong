import { apiFetch } from "./api";

export type ActionEventType = "row.created" | "row.updated" | "row.deleted";
export type ActionTargetType = "workflow" | "agent";

export interface ActionBinding {
  id: string;
  name: string;
  database_id: string;
  event_type: ActionEventType;
  target_type: ActionTargetType;
  workflow_id: string | null;
  agent_id: string | null;
  notify_user_ids: string[];
  is_active: boolean;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface CreateActionInput {
  name: string;
  database_id: string;
  event_type: ActionEventType;
  target_type: ActionTargetType;
  workflow_id?: string | null;
  agent_id?: string | null;
  notify_user_ids?: string[];
  is_active?: boolean;
}

export type UpdateActionInput = Partial<CreateActionInput>;

// Minimal shape of a Mini-App Database for the dropdown (endpoint already exists).
export interface MiniAppDatabaseOption {
  id: string;
  name: string;
}

export const listActions = () => apiFetch<ActionBinding[]>("/actions");
export const createAction = (input: CreateActionInput) =>
  apiFetch<ActionBinding>("/actions", { method: "POST", body: JSON.stringify(input) });
export const updateAction = (id: string, input: UpdateActionInput) =>
  apiFetch<ActionBinding>(`/actions/${id}`, { method: "PATCH", body: JSON.stringify(input) });
export const deleteAction = (id: string) =>
  apiFetch<{ id: string }>(`/actions/${id}`, { method: "DELETE" });

export const listMiniAppDatabases = () =>
  apiFetch<MiniAppDatabaseOption[]>("/mini-app-databases");
