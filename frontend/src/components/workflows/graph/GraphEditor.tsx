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
  MarkerType,
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
import TerminalNode from "./TerminalNode";
import type { RFNodeData } from "../../../lib/graphEditorState";
import { deriveRollbackEdges } from "../../../lib/rollbackEdges";
import {
  deriveTerminals,
  withActivityMeta,
  isTerminalNodeId,
} from "../../../lib/activityDiagram";
import { NODE_DND_MIME, type EdgeMode } from "./PaletteSidebar";

// Directed arrowhead shared by every forward transition edge — gives the
// canvas the readable, top-down flow of a drawio activity diagram.
const FORWARD_MARKER = {
  type: MarkerType.ArrowClosed,
  width: 16,
  height: 16,
  color: "var(--color-text-secondary, #475569)",
};

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
  const nodeTypes = useMemo<NodeTypes>(() => ({ agent: AgentNode, terminal: TerminalNode }), []);
  const { screenToFlowPosition } = useReactFlow();

  // Real (editable) nodes carry in/out degree so AgentNode can flag decision /
  // merge points; synthetic START/END terminals are appended for display only.
  const renderedNodes = useMemo(() => {
    const withMeta = withActivityMeta(nodes, edges);
    const terminals = deriveTerminals(nodes, edges);
    // Terminal nodes carry TerminalNodeData, not RFNodeData, but they only ever
    // render through TerminalNode (type: "terminal") — never AgentNode — so
    // widening the array to the RFNodeData-pinned prop is safe.
    return [...withMeta, ...terminals.nodes] as Node<RFNodeData>[];
  }, [nodes, edges]);

  const renderedEdges = useMemo(() => {
    const rollback = deriveRollbackEdges(nodes, edges);
    const terminals = deriveTerminals(nodes, edges);
    const rollbackMode = edgeMode === "rollback";
    // Dim forward edges when emphasizing rollback, and vice-versa. Every
    // forward transition gets an arrowhead + orthogonal routing.
    const forward = edges.map((e) => ({
      ...e,
      type: e.type ?? "smoothstep",
      markerEnd: e.markerEnd ?? FORWARD_MARKER,
      style: {
        stroke: "var(--color-text-secondary, #475569)",
        strokeWidth: 1.5,
        ...(e.style ?? {}),
        opacity: rollbackMode ? 0.25 : 1,
      },
    }));
    const overlay = rollback.map((e) => ({
      ...e,
      style: { ...(e.style ?? {}), opacity: rollbackMode ? 1 : 0.6 },
    }));
    // Terminal (start/end) edges follow the forward emphasis.
    const terminalEdges = terminals.edges.map((e) => ({
      ...e,
      style: { ...(e.style ?? {}), opacity: rollbackMode ? 0.25 : 1 },
    }));
    return [...forward, ...terminalEdges, ...overlay];
  }, [nodes, edges, edgeMode]);

  return (
    <div style={{ height: "100%", border: "1px solid var(--color-border)", borderRadius: 8 }}>
      <ReactFlow
        nodes={renderedNodes}
        edges={renderedEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(_, n) => onSelectNode(isTerminalNodeId(n.id) ? null : n.id)}
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
