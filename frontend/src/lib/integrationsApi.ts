/* Story 2.7 — API Integration API layer.
 *
 * Typed wrappers around apiFetch for the Integration endpoints: POST/GET/
 * PATCH/DELETE /agents/{id}/integrations[/{integrationId}], POST
 * .../integrations/{integrationId}/test. apiFetch injects JWT + tenant
 * headers and unwraps the {data,error,meta} envelope. `auth_header_masked`
 * is the only header representation the backend ever returns (AC2).
 */

import { apiFetch } from "./api";

/** Mirrors the Story 2.7 `serialize_integration` response shape — header masked. */
export interface ApiIntegration {
  id: string;
  agent_id: string;
  name: string;
  base_url: string;
  auth_header_masked: string;
  schema: Record<string, unknown> | null;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateIntegrationInput {
  name: string;
  base_url: string;
  auth_header: string;
  schema?: Record<string, unknown> | null;
}

export interface UpdateIntegrationInput {
  name?: string;
  base_url?: string;
  auth_header?: string;
  schema?: Record<string, unknown> | null;
}

/** The Test Integration affordance result (AC9) — never includes the header. */
export interface IntegrationTestResult {
  status: "connected" | "disconnected";
  status_code: number;
  latency_ms: number;
}

export function listIntegrations(agentId: string): Promise<ApiIntegration[]> {
  return apiFetch<ApiIntegration[]>(`/agents/${agentId}/integrations`);
}

export function createIntegration(
  agentId: string,
  input: CreateIntegrationInput,
): Promise<ApiIntegration> {
  return apiFetch<ApiIntegration>(`/agents/${agentId}/integrations`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateIntegration(
  agentId: string,
  integrationId: string,
  patch: UpdateIntegrationInput,
): Promise<ApiIntegration> {
  return apiFetch<ApiIntegration>(`/agents/${agentId}/integrations/${integrationId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function deleteIntegration(
  agentId: string,
  integrationId: string,
): Promise<{ id: string }> {
  return apiFetch<{ id: string }>(`/agents/${agentId}/integrations/${integrationId}`, {
    method: "DELETE",
  });
}

export function testIntegration(
  agentId: string,
  integrationId: string,
): Promise<IntegrationTestResult> {
  return apiFetch<IntegrationTestResult>(
    `/agents/${agentId}/integrations/${integrationId}/test`,
    { method: "POST" },
  );
}
