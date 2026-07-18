/* Sub-project 3C — Run tracking + review API layer.
 *
 * Typed wrappers around apiFetch for the run-execution endpoints:
 *   - Story 3.2 run CRUD (POST/GET /workflows/{id}/runs, GET /workflows/runs/{id})
 *   - 3C topology (GET /workflows/runs/{id}/graph)
 *   - 3B review (GET /workflows/runs/{id}/nodes, POST decision, POST rollback confirm)
 * apiFetch injects JWT + tenant headers and unwraps {data,error,meta}.
 */

import { apiFetch } from "./api";

export type RunStatus =
  | "pending"
  | "running"
  | "awaiting_human"
  | "completed"
  | "failed"
  | "timed_out"
  | "completed_with_failures";

export type NodeStatus =
  | "pending"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed"
  | "rejected"
  | "skipped"
  | "rolled_back";

export interface Run {
  id: string;
  tenant_id: string;
  workflow_id: string;
  status: RunStatus;
  input: Record<string, unknown>;
  result: Record<string, unknown> | null;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
}

export interface GraphNode {
  node_key: string;
  label: string;
  agent_id: string;
  config: Record<string, unknown>;
  position: { x: number; y: number };
  approver_user_ids: string[];
}

export interface GraphEdge {
  from: string;
  to: string;
}

export interface GraphSnapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface RunNodeExecution {
  id: string;
  run_id: string;
  node_key: string;
  agent_id: string;
  status: NodeStatus;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  approver_user_ids: string[];
  decision: string | null;
  decided_by: string | null;
  reason: string | null;
  guidance: string | null;
  decided_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface RollbackRequest {
  id: string;
  requester_node_key: string;
  target_node_key: string;
  reason: string | null;
  status: string;
}

export interface RunNodesResponse {
  nodes: RunNodeExecution[];
  rollbacks: { pending: RollbackRequest[]; refused: RollbackRequest[] };
}

export type DecisionAction = "approve" | "retry" | "override" | "reject";

export interface DecisionRequest {
  action: DecisionAction;
  guidance?: string;
  output?: Record<string, unknown>;
  reason?: string;
  target_node_key?: string;
}

export function createRun(
  workflowId: string,
  input: Record<string, unknown>,
): Promise<Run> {
  return apiFetch<Run>(`/workflows/${workflowId}/runs`, {
    method: "POST",
    body: JSON.stringify({ input }),
  });
}

export function listRuns(workflowId: string): Promise<Run[]> {
  return apiFetch<Run[]>(`/workflows/${workflowId}/runs`);
}

export function getRun(runId: string): Promise<Run> {
  return apiFetch<Run>(`/workflows/runs/${runId}`);
}

export function getRunGraph(runId: string): Promise<GraphSnapshot> {
  return apiFetch<GraphSnapshot>(`/workflows/runs/${runId}/graph`);
}

export function listRunNodes(runId: string): Promise<RunNodesResponse> {
  return apiFetch<RunNodesResponse>(`/workflows/runs/${runId}/nodes`);
}

export function postDecision(
  runId: string,
  nodeKey: string,
  body: DecisionRequest,
): Promise<RunNodeExecution> {
  return apiFetch<RunNodeExecution>(
    `/workflows/runs/${runId}/nodes/${nodeKey}/decision`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function confirmRollback(
  runId: string,
  rollbackId: string,
  accept: boolean,
): Promise<{ id: string; status: string }> {
  return apiFetch<{ id: string; status: string }>(
    `/workflows/runs/${runId}/rollbacks/${rollbackId}/confirm`,
    { method: "POST", body: JSON.stringify({ accept }) },
  );
}
