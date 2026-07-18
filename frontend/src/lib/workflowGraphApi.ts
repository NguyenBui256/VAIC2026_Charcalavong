/* 3D — Workflow graph authoring API (GET/PUT /workflows/{id}/graph-definition).
 * Distinct from runsApi's run-graph read; this is the editable definition. */

import { apiFetch } from "./api";

export interface GraphDefinitionNode {
  node_key: string;
  label: string;
  agent_id: string;
  config: Record<string, unknown>;
  position: { x: number; y: number };
  approver_user_ids: string[];
}

export interface GraphDefinitionEdge {
  from: string;
  to: string;
}

export interface GraphDefinition {
  nodes: GraphDefinitionNode[];
  edges: GraphDefinitionEdge[];
}

export function getWorkflowGraph(workflowId: string): Promise<GraphDefinition> {
  return apiFetch<GraphDefinition>(`/workflows/${workflowId}/graph-definition`);
}

export function putWorkflowGraph(
  workflowId: string,
  def: GraphDefinition,
): Promise<GraphDefinition> {
  return apiFetch<GraphDefinition>(`/workflows/${workflowId}/graph-definition`, {
    method: "PUT",
    body: JSON.stringify(def),
  });
}
