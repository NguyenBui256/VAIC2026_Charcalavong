/* 3C — one node box on the canvas. Absolutely positioned; shows label, status
 * badge, a gated indicator (has approvers), and highlights selection / pending
 * rollback. Click selects.
 */
import RunStatusBadge from "./RunStatusBadge";
import { NODE_H, NODE_W } from "./layout";
import type { MergedNode } from "./mergeNodes";

export interface RunNodeProps {
  node: MergedNode;
  x: number;
  y: number;
  selected: boolean;
  hasPendingRollback: boolean;
  onSelect: (nodeKey: string) => void;
}

export default function RunNode({
  node,
  x,
  y,
  selected,
  hasPendingRollback,
  onSelect,
}: RunNodeProps) {
  const status = node.exec?.status ?? "pending";
  const gated = node.approver_user_ids.length > 0;
  const border = hasPendingRollback
    ? "var(--color-error)"
    : selected
      ? "var(--color-accent)"
      : "var(--color-border)";
  return (
    <button
      type="button"
      data-testid={`vaic-run-node-${node.node_key}`}
      onClick={() => onSelect(node.node_key)}
      className="vaic-focusable"
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: NODE_W,
        height: NODE_H,
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-1)",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "var(--space-2)",
        borderRadius: "var(--radius-md, 8px)",
        border: `2px solid ${border}`,
        background: "var(--color-surface)",
        cursor: "pointer",
        textAlign: "left",
      }}
    >
      <span className="text-body" style={{ fontWeight: 600 }}>
        {node.label || node.node_key}
        {gated ? " ●" : ""}
      </span>
      <RunStatusBadge status={status} />
    </button>
  );
}
