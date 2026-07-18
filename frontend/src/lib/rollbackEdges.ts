/* Frontend-only derived rollback overlay edges.
 * A gated node (>=1 approver) can, at RUN time, be rejected and rolled back to
 * a parent node (RunRollbackRequest). This module renders that possibility as
 * dashed warning-colored edges going in reverse (child -> each direct parent).
 * These are DISPLAY-ONLY: id-prefixed `rb:`, never selectable/deletable, never
 * added to `edges` state, never serialized to the API. Pure (no React). */

import type { Node, Edge } from "@xyflow/react";
import type { RFNodeData } from "./graphEditorState";

export const ROLLBACK_EDGE_ID_PREFIX = "rb:";

/** For each gated node, one dashed reverse edge to each of its direct parents. */
export function deriveRollbackEdges(
  nodes: Node<RFNodeData>[],
  edges: Edge[],
): Edge[] {
  const gated = new Set(
    nodes.filter((n) => (n.data.approverUserIds?.length ?? 0) > 0).map((n) => n.id),
  );
  const out: Edge[] = [];
  for (const e of edges) {
    // e: parent(source) -> child(target). If child is gated, it can roll back
    // to this parent, so draw child -> parent as a dashed overlay.
    if (gated.has(e.target)) {
      out.push({
        id: `${ROLLBACK_EDGE_ID_PREFIX}${e.target}->${e.source}`,
        source: e.target,
        target: e.source,
        selectable: false,
        deletable: false,
        focusable: false,
        style: {
          stroke: "var(--color-warning, #b45309)",
          strokeDasharray: "6 4",
          strokeWidth: 1.5,
        },
        label: "rollback",
        labelStyle: { fill: "var(--color-warning, #b45309)", fontSize: 10 },
        // curved so it visually separates from the solid forward edge
        type: "default",
      });
    }
  }
  return out;
}
