/* 3D — controlled React Flow canvas. Parent (GraphTab) owns forward node/edge
 * state; this renders it, merges the DISPLAY-ONLY rollback overlay, handles
 * palette drops, and reports selection. Wrapped in ReactFlowProvider so
 * screenToFlowPosition is available for accurate drop placement. */
import { useMemo } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  useReactFlow,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  type NodeTypes,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import AgentNode from "./AgentNode";
import type { RFNodeData } from "../../../lib/graphEditorState";
import { deriveRollbackEdges } from "../../../lib/rollbackEdges";
import { NODE_DND_MIME, type EdgeMode } from "./PaletteSidebar";

export type DropPayload =
  | { kind: "agent"; agentId: string; name: string }
  | { kind: "blank" };

export interface GraphEditorProps {
  nodes: Node<RFNodeData>[];
  edges: Edge[];
  edgeMode: EdgeMode;
  onNodesChange: OnNodesChange<Node<RFNodeData>>;
  onEdgesChange: OnEdgesChange;
  onConnect: OnConnect;
  onSelectNode: (id: string | null) => void;
  onDropNode: (payload: DropPayload, position: { x: number; y: number }) => void;
}

function Canvas(props: GraphEditorProps) {
  const {
    nodes, edges, edgeMode,
    onNodesChange, onEdgesChange, onConnect, onSelectNode, onDropNode,
  } = props;
  const nodeTypes = useMemo<NodeTypes>(() => ({ agent: AgentNode }), []);
  const { screenToFlowPosition } = useReactFlow();

  const renderedEdges = useMemo(() => {
    const rollback = deriveRollbackEdges(nodes, edges);
    const rollbackMode = edgeMode === "rollback";
    // Dim forward edges when emphasizing rollback, and vice-versa.
    const forward = edges.map((e) => ({
      ...e,
      style: { ...(e.style ?? {}), opacity: rollbackMode ? 0.25 : 1 },
    }));
    const overlay = rollback.map((e) => ({
      ...e,
      style: { ...(e.style ?? {}), opacity: rollbackMode ? 1 : 0.6 },
    }));
    return [...forward, ...overlay];
  }, [nodes, edges, edgeMode]);

  return (
    <div style={{ height: 560, border: "1px solid var(--color-border)", borderRadius: 8 }}>
      <ReactFlow
        nodes={nodes}
        edges={renderedEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(_, n) => onSelectNode(n.id)}
        onPaneClick={() => onSelectNode(null)}
        onDragOver={(e) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = "copy";
        }}
        onDrop={(e) => {
          e.preventDefault();
          const raw = e.dataTransfer.getData(NODE_DND_MIME);
          if (!raw) return;
          const payload = JSON.parse(raw) as DropPayload;
          const position = screenToFlowPosition({ x: e.clientX, y: e.clientY });
          onDropNode(payload, position);
        }}
        fitView
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}

export default function GraphEditor(props: GraphEditorProps) {
  return (
    <ReactFlowProvider>
      <Canvas {...props} />
    </ReactFlowProvider>
  );
}
