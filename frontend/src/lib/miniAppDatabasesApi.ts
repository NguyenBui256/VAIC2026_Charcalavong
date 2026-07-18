import { apiFetch } from "./api";

export type FieldType =
  | "string" | "longtext" | "integer" | "number" | "boolean" | "date" | "enum";

export interface SchemaField {
  name: string;
  type: FieldType;
  label?: string;
  required?: boolean;
  options?: string[];
}

export interface EntitySchema {
  fields: SchemaField[];
  primary_display?: string | null;
}

export interface MiniAppDatabase {
  id: string;
  name: string;
  description: string;
  entity_schema: EntitySchema;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface MiniAppDatabaseRow {
  row_id: string;
  app_id: string;
  data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CreateDatabaseInput {
  name: string;
  description?: string;
  entity_schema: EntitySchema;
}

export interface UpdateDatabaseInput {
  name?: string;
  description?: string;
  entity_schema?: EntitySchema;
}

export const listDatabases = () => apiFetch<MiniAppDatabase[]>("/mini-app-databases");
export const getDatabase = (id: string) => apiFetch<MiniAppDatabase>(`/mini-app-databases/${id}`);
export const createDatabase = (input: CreateDatabaseInput) =>
  apiFetch<MiniAppDatabase>("/mini-app-databases", { method: "POST", body: JSON.stringify(input) });
export const updateDatabase = (id: string, input: UpdateDatabaseInput) =>
  apiFetch<MiniAppDatabase>(`/mini-app-databases/${id}`, { method: "PATCH", body: JSON.stringify(input) });
export const deleteDatabase = (id: string) =>
  apiFetch<{ id: string }>(`/mini-app-databases/${id}`, { method: "DELETE" });
export const listDatabaseRows = (id: string) =>
  apiFetch<MiniAppDatabaseRow[]>(`/mini-app-databases/${id}/rows`);
