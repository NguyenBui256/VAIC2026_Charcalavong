/* Story 2.2 — Agent API layer.
 *
 * Typed wrappers around apiFetch (Story 1.8) for the Agent endpoints
 * delivered by Story 2.1: POST /agents, GET /agents/{id}, GET /agents,
 * PATCH /agents/{id}. apiFetch injects JWT + tenant headers and unwraps
 * the {data,error,meta} envelope.
 */

import { apiFetch } from "./api";

export type AgentStatus = "draft" | "active";

/** Story 2.3 (AD-7) — provider + model + free-form parameter overrides,
 * persisted as data on the Agent record. Empty object means "not configured". */
export interface ModelRef {
  provider: string;
  model_name: string;
  parameters: Record<string, unknown>;
}

/** Mirrors the Story 2.1/2.3 Agent record shape. */
export interface Agent {
  id: string;
  tenant_id: string;
  department_id: string;
  owner_id: string;
  name: string;
  system_prompt: string;
  model: ModelRef | Record<string, never>;
  status: AgentStatus;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface AgentListParams {
  department_id?: string;
  q?: string;
}

export interface CreateAgentInput {
  name: string;
  department_id: string;
  system_prompt: string;
  status?: AgentStatus;
}

export interface UpdateAgentInput {
  name?: string;
  department_id?: string;
  system_prompt?: string;
  status?: AgentStatus;
  model?: ModelRef;
}

function buildQuery(params: Record<string, string | undefined>): string {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) usp.set(key, value);
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export function listAgents(params: AgentListParams = {}): Promise<Agent[]> {
  const qs = buildQuery({ department_id: params.department_id, q: params.q });
  return apiFetch<Agent[]>(`/agents${qs}`);
}

export function getAgent(id: string): Promise<Agent> {
  return apiFetch<Agent>(`/agents/${id}`);
}

export function createAgent(input: CreateAgentInput): Promise<Agent> {
  return apiFetch<Agent>("/agents", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateAgent(id: string, patch: UpdateAgentInput): Promise<Agent> {
  return apiFetch<Agent>(`/agents/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

/** Story 2.3 T1 — runtime provider/model catalog (`GET /agents/providers`).
 * The frontend never hard-codes providers/models; it renders this (AD-7, FR-5). */
export interface ProviderModel {
  name: string;
  context_window: number;
}

export interface ProviderCatalogEntry {
  id: string;
  label: string;
  configured: boolean;
  models: ProviderModel[];
}

export function listProviders(): Promise<ProviderCatalogEntry[]> {
  return apiFetch<ProviderCatalogEntry[]>("/agents/providers");
}
