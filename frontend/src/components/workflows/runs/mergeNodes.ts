/* 3C — pure helpers: merge immutable topology with polled runtime node state
 * by node_key, and derive a node's parents from the edge list (reject picker).
 */
import type { GraphEdge, GraphNode, RunNodeExecution } from "../../../lib/runsApi";

export type MergedNode = GraphNode & { exec: RunNodeExecution | null };

export function mergeNodes(
  graphNodes: GraphNode[],
  execs: RunNodeExecution[],
): MergedNode[] {
  const byKey = new Map(execs.map((e) => [e.node_key, e]));
  return graphNodes.map((n) => ({ ...n, exec: byKey.get(n.node_key) ?? null }));
}

export function parentsOf(nodeKey: string, edges: GraphEdge[]): string[] {
  return edges.filter((e) => e.to === nodeKey).map((e) => e.from);
}
