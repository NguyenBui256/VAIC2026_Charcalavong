/* Shared pool — tenant-level Integration API layer.
 *
 * Typed wrappers around apiFetch for the pool Integration endpoints: POST/GET/
 * PATCH/DELETE /integrations[/{integrationId}], POST
 * .../integrations/{integrationId}/test. apiFetch injects JWT + tenant
 * headers and unwraps the {data,error,meta} envelope. `auth_header_masked`
 * is the only header representation the backend ever returns.
 */

import { apiFetch } from "./api";

/** Mirrors the `serialize_integration` response shape — header masked. */
export interface ApiIntegration {
  id: string;
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

/** The Test Integration affordance result — never includes the header. */
export interface IntegrationTestResult {
  status: "connected" | "disconnected";
  status_code: number;
  latency_ms: number;
}

export function listIntegrations(): Promise<ApiIntegration[]> {
  return apiFetch<ApiIntegration[]>(`/integrations`);
}

export function createIntegration(input: CreateIntegrationInput): Promise<ApiIntegration> {
  return apiFetch<ApiIntegration>(`/integrations`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateIntegration(
  id: string,
  patch: UpdateIntegrationInput,
): Promise<ApiIntegration> {
  return apiFetch<ApiIntegration>(`/integrations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export function deleteIntegration(id: string): Promise<{ id: string }> {
  return apiFetch<{ id: string }>(`/integrations/${id}`, {
    method: "DELETE",
  });
}

export function testIntegration(id: string): Promise<IntegrationTestResult> {
  return apiFetch<IntegrationTestResult>(`/integrations/${id}/test`, {
    method: "POST",
  });
}
