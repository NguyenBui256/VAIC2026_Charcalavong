/* Frontend-only, DISPLAY-ONLY "activity diagram" overlay for the workflow graph.
 * Mirrors the rollbackEdges pattern: derives START / END terminal nodes and
 * their connecting edges from the graph's roots (in-degree 0) and leaves
 * (out-degree 0), plus per-node in/out degree so the agent (action) nodes can
 * flag decision (branch) and merge points — giving the canvas the intuitive
 * shape vocabulary of a drawio activity diagram.
 *
 * Everything here is DISPLAY-ONLY: terminal node ids are prefixed `__`, edges
 * are prefixed `__term__`, none are selectable/deletable, and none are ever
 * written back to `nodes`/`edges` state or serialized to the API. Pure (no React). */

import { MarkerType, type Node, type Edge } from "@xyflow/react";
import type { RFNodeData } from "./graphEditorState";

export const START_NODE_ID = "__start__";
export const END_NODE_ID = "__end__";
export const TERMINAL_EDGE_ID_PREFIX = "__term__";

/** True for synthetic (start/end) nodes that must not be selected or edited. */
export function isTerminalNodeId(id: string): boolean {
  return id === START_NODE_ID || id === END_NODE_ID;
}

// Approximate agent-node box used only to center/offset the terminal circles.
const NODE_W = 190;
const NODE_H = 74;
const TERMINAL_W = 44;
const TERMINAL_H = 58; // 40px circle + gap + caption

export interface TerminalNodeData extends Record<string, unknown> {
  terminal: "start" | "end";
}

interface Degree {
  inDegree: number;
  outDegree: number;
}

/** In/out degree per real node id (ignores synthetic/overlay edges). */
export function computeDegrees(
  nodes: Node<RFNodeData>[],
  edges: Edge[],
): Map<string, Degree> {
  const deg = new Map<string, Degree>(
    nodes.map((n) => [n.id, { inDegree: 0, outDegree: 0 }]),
  );
  for (const e of edges) {
    const s = deg.get(e.source);
    if (s) s.outDegree += 1;
    const t = deg.get(e.target);
    if (t) t.inDegree += 1;
  }
  return deg;
}

/** Return the agent nodes with in/out degree merged into `data` so AgentNode
 * can render decision/merge cues. Does not mutate the inputs. */
export function withActivityMeta(
  nodes: Node<RFNodeData>[],
  edges: Edge[],
): Node<RFNodeData>[] {
  const deg = computeDegrees(nodes, edges);
  return nodes.map((n) => {
    const d = deg.get(n.id) ?? { inDegree: 0, outDegree: 0 };
    return { ...n, data: { ...n.data, inDegree: d.inDegree, outDegree: d.outDegree } };
  });
}

function avg(xs: number[]): number {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0;
}

function terminalNode(id: string, kind: "start" | "end", x: number, y: number): Node<TerminalNodeData> {
  return {
    id,
    type: "terminal",
    position: { x, y },
    data: { terminal: kind },
    // Explicit dimensions are REQUIRED: these nodes are injected downstream of
    // the parent's controlled node state, so React Flow's measured-dimension
    // change can't round-trip back. Without `measured`, RF keeps them
    // visibility:hidden and excludes them from fitView. width/height mirror the
    // TerminalNode box (circle + caption) so bounds/centering stay correct.
    width: TERMINAL_W,
    height: TERMINAL_H,
    measured: { width: TERMINAL_W, height: TERMINAL_H },
    selectable: false,
    draggable: false,
    deletable: false,
    focusable: false,
    connectable: false,
    zIndex: 0,
  };
}

function terminalEdge(source: string, target: string): Edge {
  return {
    id: `${TERMINAL_EDGE_ID_PREFIX}${source}->${target}`,
    source,
    target,
    type: "smoothstep",
    selectable: false,
    deletable: false,
    focusable: false,
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 16,
      height: 16,
      color: "var(--color-text-tertiary, #64748B)",
    },
    style: { stroke: "var(--color-text-tertiary, #64748B)", strokeWidth: 1.5 },
    zIndex: 0,
  };
}

/** Synthetic START/END nodes + their edges, positioned relative to the roots
 * and leaves of the current layout. Empty when there are no nodes. */
export function deriveTerminals(
  nodes: Node<RFNodeData>[],
  edges: Edge[],
): { nodes: Node<TerminalNodeData>[]; edges: Edge[] } {
  if (nodes.length === 0) return { nodes: [], edges: [] };
  const deg = computeDegrees(nodes, edges);
  const roots = nodes.filter((n) => (deg.get(n.id)?.inDegree ?? 0) === 0);
  const leaves = nodes.filter((n) => (deg.get(n.id)?.outDegree ?? 0) === 0);

  const outNodes: Node<TerminalNodeData>[] = [];
  const outEdges: Edge[] = [];
  const centerOffset = NODE_W / 2 - TERMINAL_W / 2;

  if (roots.length) {
    const x = avg(roots.map((r) => r.position.x)) + centerOffset;
    const y = Math.min(...roots.map((r) => r.position.y)) - 90;
    outNodes.push(terminalNode(START_NODE_ID, "start", x, y));
    for (const r of roots) outEdges.push(terminalEdge(START_NODE_ID, r.id));
  }
  if (leaves.length) {
    const x = avg(leaves.map((l) => l.position.x)) + centerOffset;
    const y = Math.max(...leaves.map((l) => l.position.y)) + NODE_H + 56;
    outNodes.push(terminalNode(END_NODE_ID, "end", x, y));
    for (const l of leaves) outEdges.push(terminalEdge(l.id, END_NODE_ID));
  }
  return { nodes: outNodes, edges: outEdges };
}
