/* 3D — pure transforms between React Flow state and the API GraphDefinition,
 * plus a client-side mirror of assert_valid_graph for pre-Save feedback.
 * No React here so it is trivially unit-testable. */

import type { Node, Edge } from "@xyflow/react";
import type { GraphDefinition } from "./workflowGraphApi";

export interface RFNodeData extends Record<string, unknown> {
  label: string;
  agentId: string;
  nodeKey: string;
  approverUserIds: string[];
}

export function toReactFlow(def: GraphDefinition): {
  nodes: Node<RFNodeData>[];
  edges: Edge[];
} {
  const nodes = def.nodes.map((n) => ({
    id: n.node_key,
    type: "agent",
    position: { x: n.position.x, y: n.position.y },
    data: {
      label: n.label,
      agentId: n.agent_id,
      nodeKey: n.node_key,
      approverUserIds: n.approver_user_ids,
    },
  }));
  const edges = def.edges.map((e) => ({
    id: `${e.from}->${e.to}`,
    source: e.from,
    target: e.to,
  }));
  return { nodes, edges };
}

export function toDefinition(
  nodes: Node<RFNodeData>[],
  edges: Edge[],
): GraphDefinition {
  return {
    nodes: nodes.map((n) => ({
      node_key: n.data.nodeKey,
      label: n.data.label,
      agent_id: n.data.agentId,
      config: {},
      position: { x: n.position.x, y: n.position.y },
      approver_user_ids: n.data.approverUserIds,
    })),
    edges: edges.map((e) => ({ from: e.source, to: e.target })),
  };
}

export function nextNodeKey(existingKeys: string[]): string {
  let i = existingKeys.length + 1;
  const set = new Set(existingKeys);
  while (set.has(`n${i}`)) i += 1;
  return `n${i}`;
}

/** Mirror of assert_valid_graph: returns the first error message, or null. */
export function validateGraph(def: GraphDefinition): string | null {
  const keys = def.nodes.map((n) => n.node_key);
  const seen = new Set<string>();
  for (const k of keys) {
    if (!k) return "a node has an empty key";
    if (seen.has(k)) return `duplicate node key: ${k}`;
    seen.add(k);
  }
  for (const n of def.nodes) {
    if (!n.agent_id) return `node "${n.node_key}" has no agent`;
  }
  const edgeSeen = new Set<string>();
  for (const e of def.edges) {
    if (!seen.has(e.from)) return `edge from unknown node: ${e.from}`;
    if (!seen.has(e.to)) return `edge to unknown node: ${e.to}`;
    if (e.from === e.to) return `self-loop on node: ${e.from}`;
    const id = `${e.from}->${e.to}`;
    if (edgeSeen.has(id)) return `duplicate edge: ${e.from} -> ${e.to}`;
    edgeSeen.add(id);
  }
  // Kahn cycle check.
  const indeg = new Map(keys.map((k) => [k, 0]));
  const adj = new Map<string, string[]>(keys.map((k) => [k, []]));
  for (const e of def.edges) {
    indeg.set(e.to, (indeg.get(e.to) ?? 0) + 1);
    adj.get(e.from)?.push(e.to);
  }
  const queue = keys.filter((k) => (indeg.get(k) ?? 0) === 0);
  let consumed = 0;
  while (queue.length) {
    const k = queue.shift() as string;
    consumed += 1;
    for (const c of adj.get(k) ?? []) {
      indeg.set(c, (indeg.get(c) ?? 0) - 1);
      if ((indeg.get(c) ?? 0) === 0) queue.push(c);
    }
  }
  if (consumed !== keys.length) return "graph contains a cycle";
  return null;
}
