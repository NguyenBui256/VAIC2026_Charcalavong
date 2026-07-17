/* Story 2.6 — Tool API layer.
 *
 * Typed wrappers around apiFetch for the Tool endpoints: POST/GET/PATCH/DELETE
 * /agents/{id}/tools[/{toolId}], POST .../tools/{toolId}/test. apiFetch
 * injects JWT + tenant headers and unwraps the {data,error,meta} envelope.
 */

import { apiFetch } from "./api";

export type ToolKind = "mcp" | "embedded_python";

/** Mirrors the Story 2.6 `serialize_tool` response shape — `header` masked. */
export interface Tool {
  id: string;
  agent_id: string;
  display_name: string;
  header: { auth?: boolean };
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  has_embedded_python: boolean;
  kind: ToolKind;
  created_at: string;
  updated_at: string;
}

export interface CreateToolInput {
  display_name: string;
  header?: Record<string, unknown>;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  embedded_python?: string | null;
}

export interface UpdateToolInput {
  display_name?: string;
  header?: Record<string, unknown>;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  embedded_python?: string | null;
}

/** Mirrors backend `ToolOutput` — the Test Tool affordance result (AC7). */
export interface ToolTestResult {
  tool_name: string;
  output: Record<string, unknown>;
  success: boolean;
  error: string;
  latency_ms: number;
}

export function listTools(agentId: string): Promise<Tool[]> {
  return apiFetch<Tool[]>(`/agents/${agentId}/tools`);
}

export function createTool(agentId: string, input: CreateToolInput): Promise<Tool> {
  return apiFetch<Tool>(`/agents/${agentId}/tools`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateTool(
  agentId: string,
  toolId: string,
  patch: UpdateToolInput,
): Promise<Tool> {
  return apiFetch<Tool>(`/agents/${agentId}/tools/${toolId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function deleteTool(agentId: string, toolId: string): Promise<{ id: string }> {
  return apiFetch<{ id: string }>(`/agents/${agentId}/tools/${toolId}`, {
    method: "DELETE",
  });
}

export function testTool(
  agentId: string,
  toolId: string,
  sampleInput: Record<string, unknown>,
): Promise<ToolTestResult> {
  return apiFetch<ToolTestResult>(`/agents/${agentId}/tools/${toolId}/test`, {
    method: "POST",
    body: JSON.stringify({ sample_input: sampleInput }),
  });
}
