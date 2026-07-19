import { useMemo } from "react";
import {
  Background, Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { AuditGraph, AuditSpan } from "./types";
import AuditStatusPill from "./AuditStatus";

type TraceNode = Node<{ span: AuditSpan }, "trace">;

function TraceNodeView({ data }: NodeProps<TraceNode>) {
  const { span } = data;
  return (
    <div className={`audit-graph-node audit-node-${span.status}`} tabIndex={0} aria-label={`${span.name}, ${span.status}`}>
      <Handle type="target" position={Position.Top} />
      <div className="audit-node-type">{span.node_type}</div>
      <strong>{span.name}</strong>
      <div className="audit-node-meta">
        <AuditStatusPill status={span.status} />
        <span>{span.duration_ms == null ? "live" : `${span.duration_ms}ms`}</span>
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

const nodeTypes = { trace: TraceNodeView };

function layout(spans: AuditSpan[]): TraceNode[] {
  const byParent = new Map<string, AuditSpan[]>();
  const ids = new Set(spans.map((span) => span.id));
  for (const span of spans) {
    const key = span.parent_span_id && ids.has(span.parent_span_id) ? span.parent_span_id : "root";
    byParent.set(key, [...(byParent.get(key) ?? []), span]);
  }
  const result: TraceNode[] = [];
  let leafColumn = 0;
  const visit = (span: AuditSpan, depth: number): number => {
    const children = byParent.get(span.id) ?? [];
    const childColumns = children.map((child) => visit(child, depth + 1));
    const column = childColumns.length
      ? childColumns.reduce((sum, value) => sum + value, 0) / childColumns.length
      : leafColumn++;
    result.push({
      id: span.id,
      type: "trace",
      position: { x: column * 300, y: depth * 190 },
      data: { span },
    });
    return column;
  };
  for (const root of byParent.get("root") ?? []) visit(root, 0);
  return result;
}

export default function TraceGraph({ graph, onSelect }: { graph: AuditGraph; onSelect: (span: AuditSpan) => void }) {
  const nodes = useMemo(() => layout(graph.nodes), [graph.nodes]);
  const edges = useMemo<Edge[]>(() => graph.edges.map((edge) => ({
    ...edge, animated: edge.type === "dependency", label: edge.type,
  })), [graph.edges]);
  return (
    <div className="audit-graph" role="region" aria-label="Execution graph">
      <ReactFlow<TraceNode, Edge>
        nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView minZoom={0.2}
        onNodeClick={(_, node) => onSelect(node.data.span)} nodesDraggable={false}
      >
        <Background /><Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
