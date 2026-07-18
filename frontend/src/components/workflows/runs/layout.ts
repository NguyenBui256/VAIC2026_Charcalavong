/* 3C — canvas geometry. Uses stored node positions; if every node sits at the
 * same spot (missing/degenerate positions in older snapshots), falls back to a
 * BFS-depth column layout so nodes don't overlap.
 */
import type { GraphEdge } from "../../../lib/runsApi";
import type { MergedNode } from "./mergeNodes";

export const NODE_W = 180;
export const NODE_H = 72;
const COL_GAP = 240;
const ROW_GAP = 120;

function positionsCollapsed(nodes: MergedNode[]): boolean {
  if (nodes.length <= 1) return false;
  const first = nodes[0].position;
  return nodes.every(
    (n) => n.position.x === first.x && n.position.y === first.y,
  );
}

/** BFS depth (column index) per node from the roots. */
function depths(nodes: MergedNode[], edges: GraphEdge[]): Map<string, number> {
  const parents = new Map<string, number>();
  nodes.forEach((n) => parents.set(n.node_key, 0));
  edges.forEach((e) => parents.set(e.to, (parents.get(e.to) ?? 0) + 1));
  const adj = new Map<string, string[]>();
  nodes.forEach((n) => adj.set(n.node_key, []));
  edges.forEach((e) => adj.get(e.from)?.push(e.to));

  const depth = new Map<string, number>();
  const queue = nodes.filter((n) => (parents.get(n.node_key) ?? 0) === 0)
    .map((n) => n.node_key);
  queue.forEach((k) => depth.set(k, 0));
  while (queue.length) {
    const k = queue.shift() as string;
    const d = depth.get(k) ?? 0;
    for (const child of adj.get(k) ?? []) {
      if (!depth.has(child) || (depth.get(child) as number) < d + 1) {
        depth.set(child, d + 1);
        queue.push(child);
      }
    }
  }
  nodes.forEach((n) => {
    if (!depth.has(n.node_key)) depth.set(n.node_key, 0);
  });
  return depth;
}

export function layoutPositions(
  nodes: MergedNode[],
  edges: GraphEdge[],
): Map<string, { x: number; y: number }> {
  const out = new Map<string, { x: number; y: number }>();
  if (!positionsCollapsed(nodes)) {
    nodes.forEach((n) => out.set(n.node_key, { x: n.position.x, y: n.position.y }));
    return out;
  }
  const depth = depths(nodes, edges);
  const rowByCol = new Map<number, number>();
  nodes.forEach((n) => {
    const col = depth.get(n.node_key) ?? 0;
    const row = rowByCol.get(col) ?? 0;
    rowByCol.set(col, row + 1);
    out.set(n.node_key, { x: 40 + col * COL_GAP, y: 40 + row * ROW_GAP });
  });
  return out;
}
