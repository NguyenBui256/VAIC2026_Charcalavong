/* 3D — custom React Flow node rendered as an activity-diagram "action": a
 * rounded card with a state accent stripe (unassigned / assigned / gated), a
 * decision-diamond badge on branch points (out-degree > 1), and a merge cue on
 * join points (in-degree > 1). Degrees are injected display-only by
 * lib/activityDiagram.withActivityMeta. */
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import type { RFNodeData } from "../../../lib/graphEditorState";
import ApproverAvatars from "./ApproverAvatars";

const handleStyle = { width: 8, height: 8, background: "var(--color-text-tertiary)", border: "none" };

/** Rotated-square decision marker with a branch count — a UML decision diamond. */
function DecisionBadge({ count }: { count: number }) {
  return (
    <div
      title={`Decision — ${count} branches`}
      style={{
        position: "relative",
        width: 20,
        height: 20,
        flexShrink: 0,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          transform: "rotate(45deg)",
          borderRadius: 3,
          background: "var(--color-surface, #fff)",
          border: "1.5px solid var(--color-primary, #4F46E5)",
        }}
      />
      <span
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 10,
          fontWeight: 700,
          color: "var(--color-primary, #4F46E5)",
        }}
      >
        {count}
      </span>
    </div>
  );
}

export default function AgentNode({ data, selected }: NodeProps<Node<RFNodeData>>) {
  const approvers = data.approverUserIds ?? [];
  const gated = approvers.length > 0;
  const hasAgent = Boolean(data.agentId);
  const outDegree = data.outDegree ?? 0;
  const inDegree = data.inDegree ?? 0;
  const isDecision = outDegree > 1;
  const isMerge = inDegree > 1;

  const accent = gated
    ? "var(--color-warning, #b45309)"
    : hasAgent
      ? "var(--color-primary, #4F46E5)"
      : "var(--color-border-strong, #CBD5E1)";

  return (
    <div
      style={{
        position: "relative",
        width: 190,
        borderRadius: 12,
        border: `1px solid var(--color-border${selected ? "-strong" : ""}, #CBD5E1)`,
        background: "var(--color-surface, #fff)",
        boxShadow: selected
          ? "0 0 0 2px var(--color-primary-soft, #EEF2FF), 0 8px 20px rgba(15,23,42,0.14)"
          : "0 1px 3px rgba(15,23,42,0.10)",
        overflow: "hidden",
        fontSize: 13,
      }}
    >
      <Handle type="target" position={Position.Top} style={handleStyle} />

      {/* state accent stripe (left edge) */}
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 4, background: accent }} />

      <div style={{ padding: "9px 11px 9px 14px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7, minWidth: 0 }}>
            {/* action marker */}
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: 2,
                flexShrink: 0,
                background: accent,
              }}
            />
            <span
              style={{
                fontWeight: 600,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {data.label || data.nodeKey}
            </span>
          </div>
          {isDecision && <DecisionBadge count={outDegree} />}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3, flexWrap: "wrap" }}>
          <span style={{ opacity: 0.6, fontSize: 11, fontFamily: "var(--font-mono, monospace)" }}>
            {data.nodeKey}
          </span>
          {!hasAgent && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                padding: "0 6px",
                borderRadius: 999,
                color: "var(--color-text-tertiary, #64748B)",
                background: "var(--color-surface-muted, #F4F6F9)",
              }}
            >
              no agent
            </span>
          )}
          {isMerge && (
            <span
              title={`Merge — ${inDegree} incoming`}
              style={{
                fontSize: 10,
                fontWeight: 600,
                padding: "0 6px",
                borderRadius: 999,
                color: "var(--color-text-secondary, #475569)",
                background: "var(--color-surface-inset, #EEF1F6)",
              }}
            >
              merge x{inDegree}
            </span>
          )}
        </div>

        {gated && (
          <div
            style={{
              marginTop: 6,
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 11,
              color: "var(--color-warning, #b45309)",
            }}
          >
            <ApproverAvatars userIds={approvers} />
          </div>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </div>
  );
}
