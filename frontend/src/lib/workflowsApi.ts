/* Story 3.1 — Workflow API layer.
 *
 * Typed wrappers around apiFetch (Story 1.8) for the Workflow endpoints
 * delivered by backend Story 3.1: POST /workflows, GET /workflows/{id},
 * GET /workflows, PATCH /workflows/{id}. apiFetch injects JWT + tenant
 * headers and unwraps the {data,error,meta} envelope.
 */

import { apiFetch } from "./api";

/** Mirrors the Story 3.1 Workflow record shape (backend `serialize_workflow`). */
export interface Workflow {
  id: string;
  tenant_id: string;
  owner_id: string;
  name: string;
  description: string;
  constraints: string[];
  confidence_threshold: number;
  escalation_timeout_seconds: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface WorkflowListParams {
  search?: string;
  owner_id?: string;
}

export interface CreateWorkflowInput {
  name: string;
  description: string;
  constraints?: string[];
}

export interface UpdateWorkflowInput {
  name?: string;
  description?: string;
  constraints?: string[];
  confidence_threshold?: number;
  escalation_timeout_seconds?: number;
}

function buildQuery(params: Record<string, string | undefined>): string {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) usp.set(key, value);
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export function listWorkflows(params: WorkflowListParams = {}): Promise<Workflow[]> {
  const qs = buildQuery({ search: params.search, owner_id: params.owner_id });
  return apiFetch<Workflow[]>(`/workflows${qs}`);
}

export function getWorkflow(id: string): Promise<Workflow> {
  return apiFetch<Workflow>(`/workflows/${id}`);
}

export function createWorkflow(input: CreateWorkflowInput): Promise<Workflow> {
  return apiFetch<Workflow>("/workflows", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateWorkflow(id: string, patch: UpdateWorkflowInput): Promise<Workflow> {
  return apiFetch<Workflow>(`/workflows/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}
