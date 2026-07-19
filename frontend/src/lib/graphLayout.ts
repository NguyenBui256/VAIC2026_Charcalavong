/* Frontend-only vertical auto-layout for the workflow graph.
 * Pure (no React): longest-path layering places roots at layer 0 and each
 * node at max(parent layer)+1, laid out top->bottom. Siblings in a layer are
 * spread across X and centered. Dependency-free (no dagre/elk installed). */

import type { Node, Edge } from "@xyflow/react";
import type { RFNodeData } from "./graphEditorState";

const ROW_GAP = 160; // vertical distance between layers (y)
const COL_GAP = 240; // horizontal distance between siblings (x)

/** True when every node sits at the default (0,0) — i.e. never arranged. */
export function allPositionsZero(nodes: Node<RFNodeData>[]): boolean {
  return nodes.every((n) => n.position.x === 0 && n.position.y === 0);
}

/** Assign top->bottom layered positions. Assumes a DAG (cycles are broken
 * defensively by capping the layering pass at nodes.length iterations). */
export function layoutVertical(
  nodes: Node<RFNodeData>[],
  edges: Edge[],
): Node<RFNodeData>[] {
  const ids = nodes.map((n) => n.id);
  const idSet = new Set(ids);
  const parents = new Map<string, string[]>(ids.map((id) => [id, []]));
  for (const e of edges) {
    if (idSet.has(e.source) && idSet.has(e.target)) {
      parents.get(e.target)!.push(e.source);
    }
  }

  // Longest-path layer via memoized recursion with a visiting guard.
  const layer = new Map<string, number>();
  const visiting = new Set<string>();
  function computeLayer(id: string): number {
    if (layer.has(id)) return layer.get(id)!;
    if (visiting.has(id)) return 0; // cycle guard (shouldn't happen on a DAG)
    visiting.add(id);
    const ps = parents.get(id)!;
    const l = ps.length === 0 ? 0 : Math.max(...ps.map(computeLayer)) + 1;
    visiting.delete(id);
    layer.set(id, l);
    return l;
  }
  for (const id of ids) computeLayer(id);

  // Group by layer (preserve node input order within a layer for stability).
  const byLayer = new Map<number, string[]>();
  for (const id of ids) {
    const l = layer.get(id)!;
    if (!byLayer.has(l)) byLayer.set(l, []);
    byLayer.get(l)!.push(id);
  }

  const pos = new Map<string, { x: number; y: number }>();
  for (const [l, group] of byLayer) {
    const width = (group.length - 1) * COL_GAP;
    group.forEach((id, i) => {
      pos.set(id, { x: i * COL_GAP - width / 2, y: l * ROW_GAP });
    });
  }

  return nodes.map((n) => ({ ...n, position: pos.get(n.id) ?? n.position }));
}
