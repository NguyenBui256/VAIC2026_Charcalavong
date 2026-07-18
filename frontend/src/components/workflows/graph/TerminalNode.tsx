/* 3D — display-only activity-diagram terminals: a filled initial circle (start)
 * and a bullseye final node (end), matching UML activity-diagram / drawio shapes.
 * Rendered from the synthetic nodes produced by lib/activityDiagram; never
 * selectable or serialized. */
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import type { TerminalNodeData } from "../../../lib/activityDiagram";

const handleStyle = { width: 8, height: 8, background: "var(--color-text-tertiary)", border: "none" };

export default function TerminalNode({ data }: NodeProps<Node<TerminalNodeData>>) {
  const isStart = data.terminal === "start";
  return (
    <div style={{ width: 44, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      {isStart ? (
        <Handle type="source" position={Position.Bottom} style={handleStyle} isConnectable={false} />
      ) : (
        <Handle type="target" position={Position.Top} style={handleStyle} isConnectable={false} />
      )}
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: "50%",
          border: "2px solid var(--color-text, #0F172A)",
          background: isStart ? "var(--color-text, #0F172A)" : "var(--color-surface, #fff)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: "0 1px 3px rgba(15,23,42,0.14)",
        }}
      >
        {/* end node: solid inner disc inside the ring (bullseye) */}
        {!isStart && (
          <div style={{ width: 22, height: 22, borderRadius: "50%", background: "var(--color-text, #0F172A)" }} />
        )}
      </div>
      <div
        style={{
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: 0.4,
          color: "var(--color-text-tertiary, #64748B)",
        }}
      >
        {isStart ? "START" : "END"}
      </div>
    </div>
  );
}
