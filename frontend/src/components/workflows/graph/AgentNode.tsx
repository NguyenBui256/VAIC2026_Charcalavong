/* 3D — custom React Flow node: label + bound-agent name + gated badge + approvers. */
import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { RFNode } from "../../../lib/graphEditorState";
import ApproverAvatars from "./ApproverAvatars";

export default function AgentNode({ data, selected }: NodeProps<RFNode>) {
  const approvers = data.approverUserIds ?? [];
  const gated = approvers.length > 0;
  return (
    <div
      style={{
        width: 180,
        padding: "8px 10px",
        borderRadius: 8,
        border: `1px solid var(--color-border${selected ? "-strong" : ""}, #888)`,
        background: "var(--color-surface, #fff)",
        fontSize: 13,
      }}
    >
      <Handle type="target" position={Position.Top} />
      <div style={{ fontWeight: 600 }}>{data.label || data.nodeKey}</div>
      <div style={{ opacity: 0.7, fontSize: 11 }}>{data.nodeKey}</div>
      {gated && (
        <div
          style={{
            marginTop: 4,
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 11,
            color: "var(--color-warning, #b45309)",
          }}
        >
          <span>● human-gated</span>
          <ApproverAvatars userIds={approvers} />
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
