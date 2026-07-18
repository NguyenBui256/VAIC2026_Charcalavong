/* Shared pool — tenant-level Tool catalog API layer.
 *
 * Typed wrappers around apiFetch for the pool Tool endpoints: POST/GET/
 * PATCH/DELETE /tools[/{toolId}], POST .../tools/{toolId}/test. apiFetch
 * injects JWT + tenant headers and unwraps the {data,error,meta} envelope.
 */

import { apiFetch } from "./api";

export type ToolKind = "builtin" | "integration";

/** Mirrors the backend `serialize_tool` response shape. */
export interface Tool {
  id: string;
  tool_type: string;
  display_name: string;
  description: string;
  params_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  config: Record<string, unknown> | null;
  kind: ToolKind;
  /** Registered Integration this Tool calls through, or null. */
  integration_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateToolInput {
  display_name: string;
  description: string;
  params_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  integration_id: string;
}

export interface UpdateToolInput {
  display_name?: string;
  description?: string;
  params_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  integration_id?: string;
}

/** Mirrors backend `ToolOutput` — the Test Tool affordance result. */
export interface ToolTestResult {
  tool_name: string;
  output: Record<string, unknown>;
  success: boolean;
  error: string;
  latency_ms: number;
}

export function listCatalogTools(): Promise<Tool[]> {
  return apiFetch<Tool[]>(`/tools`);
}

export function createTool(input: CreateToolInput): Promise<Tool> {
  return apiFetch<Tool>(`/tools`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateTool(id: string, patch: UpdateToolInput): Promise<Tool> {
  return apiFetch<Tool>(`/tools/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function deleteTool(id: string): Promise<{ id: string }> {
  return apiFetch<{ id: string }>(`/tools/${id}`, {
    method: "DELETE",
  });
}

export function testTool(
  id: string,
  sampleInput: Record<string, unknown>,
): Promise<ToolTestResult> {
  return apiFetch<ToolTestResult>(`/tools/${id}/test`, {
    method: "POST",
    body: JSON.stringify({ sample_input: sampleInput }),
  });
}
