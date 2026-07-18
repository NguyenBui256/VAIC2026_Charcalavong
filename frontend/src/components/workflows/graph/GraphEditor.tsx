/* 3D — controlled React Flow canvas. Parent (GraphTab) owns node/edge state;
 * this renders it, wires change/connect handlers, and reports selection. */
import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import AgentNode from "./AgentNode";
import type { RFNodeData } from "../../../lib/graphEditorState";

export interface GraphEditorProps {
  nodes: Node<RFNodeData>[];
  edges: Edge[];
  onNodesChange: OnNodesChange<Node<RFNodeData>>;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;
  onSelectNode: (id: string | null) => void;
}

export default function GraphEditor({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onSelectNode,
}: GraphEditorProps) {
  const nodeTypes = useMemo(() => ({ agent: AgentNode }), []);
  return (
    <div style={{ height: 520, border: "1px solid var(--color-border)", borderRadius: 8 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(_, n) => onSelectNode(n.id)}
        onPaneClick={() => onSelectNode(null)}
        fitView
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
