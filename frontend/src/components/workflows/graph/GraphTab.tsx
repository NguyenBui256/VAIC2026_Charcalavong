/* 3D — Graph tab: owns editor state, loads/saves the DAG, validates pre-Save. */
import { useEffect, useMemo, useState } from "react";
import {
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  type Node,
  type Edge,
  type Connection,
} from "@xyflow/react";
import { Skeleton, ErrorState, useToast } from "../../ui";
import GraphEditor, { type DropPayload } from "./GraphEditor";
import NodeInspector from "./NodeInspector";
import GraphToolbar from "./GraphToolbar";
import PaletteSidebar, { type EdgeMode } from "./PaletteSidebar";
import { GraphUsersProvider } from "./GraphUsersContext";
import { useWorkflowGraph } from "../../../hooks/useWorkflowGraph";
import { useWorkflowGraphMutation } from "../../../hooks/useWorkflowGraphMutation";
import { useUsers } from "../../../hooks/useUsers";
import { layoutVertical, allPositionsZero } from "../../../lib/graphLayout";
import {
  toReactFlow,
  toDefinition,
  nextNodeKey,
  validateGraph,
  type RFNodeData,
} from "../../../lib/graphEditorState";

export interface GraphTabProps {
  workflowId: string;
  onDirtyChange?: (dirty: boolean) => void;
}

// React Flow emits dimension/select changes on mount, fitView, and clicks;
// only these change types are genuine user edits that should mark the graph dirty.
const STRUCTURAL_NODE_CHANGES = new Set(["position", "remove", "add", "replace"]);
const STRUCTURAL_EDGE_CHANGES = new Set(["remove", "add", "replace"]);

export default function GraphTab({ workflowId, onDirtyChange }: GraphTabProps) {
  const graph = useWorkflowGraph(workflowId);
  const { mutateAsync, isPending } = useWorkflowGraphMutation(workflowId);
  const { show } = useToast();

  const [nodes, setNodes] = useState<Node<RFNodeData>[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [edgeMode, setEdgeMode] = useState<EdgeMode>("transition");
  const users = useUsers();

  // Resync baseline from server on load / after save.
  useEffect(() => {
    if (!graph.data) return;
    const rf = toReactFlow(graph.data);
    const laid = allPositionsZero(rf.nodes)
      ? layoutVertical(rf.nodes, rf.edges)
      : rf.nodes;
    setNodes(laid);
    setEdges(rf.edges);
    setDirty(false);
  }, [graph.data]);

  // Lift dirty state so the shell's unsaved-changes guard (AC7) warns before
  // a tab switch / Back navigation would discard unsaved graph edits.
  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  const def = useMemo(() => toDefinition(nodes, edges), [nodes, edges]);
  const error = useMemo(() => validateGraph(def), [def]);
  const selected = nodes.find((n) => n.id === selectedId) ?? null;

  function addNode() {
    const key = nextNodeKey(nodes.map((n) => n.data.nodeKey));
    setNodes((ns) => [
      ...ns,
      {
        id: key,
        type: "agent",
        position: { x: 80 + ns.length * 40, y: 80 + ns.length * 40 },
        data: { label: key, agentId: "", nodeKey: key, approverUserIds: [] },
      },
    ]);
    setSelectedId(key);
    setDirty(true);
  }

  function autoLayout() {
    setNodes((ns) => layoutVertical(ns, edges));
    setDirty(true);
  }

  function addNodeFromDrop(payload: DropPayload, position: { x: number; y: number }) {
    const key = nextNodeKey(nodes.map((n) => n.data.nodeKey));
    const isAgent = payload.kind === "agent";
    setNodes((ns) => [
      ...ns,
      {
        id: key,
        type: "agent",
        position,
        data: {
          label: isAgent ? payload.name : key,
          agentId: isAgent ? payload.agentId : "",
          nodeKey: key,
          approverUserIds: [],
        },
      },
    ]);
    setSelectedId(key);
    setDirty(true);
  }

  function patchSelected(patch: Partial<RFNodeData>) {
    setNodes((ns) =>
      ns.map((n) => (n.id === selectedId ? { ...n, data: { ...n.data, ...patch } } : n)),
    );
    setDirty(true);
  }

  function deleteNode(id: string) {
    setNodes((ns) => ns.filter((n) => n.id !== id));
    setEdges((es) => es.filter((e) => e.source !== id && e.target !== id));
    if (selectedId === id) setSelectedId(null);
    setDirty(true);
  }

  async function save() {
    if (error) {
      show(error, "error");
      return;
    }
    try {
      await mutateAsync(def);
      show("Graph saved");
      setDirty(false);
    } catch (e) {
      show((e as Error).message, "error");
    }
  }

  if (graph.isLoading) return <Skeleton lines={6} height="24px" />;
  if (graph.isError) return <ErrorState message={graph.error?.message ?? "Failed to load graph"} />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <GraphToolbar
        onAddNode={addNode}
        onDeleteSelected={() => selectedId && deleteNode(selectedId)}
        onSave={save}
        onReset={() => graph.data && (setNodes(toReactFlow(graph.data).nodes),
          setEdges(toReactFlow(graph.data).edges), setDirty(false))}
        saving={isPending}
        dirty={dirty}
        error={error}
      />
      <div style={{ display: "flex", gap: "var(--space-4)", alignItems: "flex-start" }}>
        <PaletteSidebar
          edgeMode={edgeMode}
          onEdgeModeChange={setEdgeMode}
          onAutoLayout={autoLayout}
        />
        <div style={{ flex: 1 }}>
          <GraphUsersProvider users={users.data ?? []}>
            <GraphEditor
              nodes={nodes}
              edges={edges}
              edgeMode={edgeMode}
              onNodesChange={(c) => {
                setNodes((ns) => applyNodeChanges(c, ns));
                if (c.some((ch) => STRUCTURAL_NODE_CHANGES.has(ch.type))) setDirty(true);
              }}
              onEdgesChange={(c) => {
                setEdges((es) => applyEdgeChanges(c, es));
                if (c.some((ch) => STRUCTURAL_EDGE_CHANGES.has(ch.type))) setDirty(true);
              }}
              onConnect={(conn: Connection) => { setEdges((es) => addEdge(conn, es)); setDirty(true); }}
              onSelectNode={setSelectedId}
              onDropNode={addNodeFromDrop}
            />
          </GraphUsersProvider>
        </div>
        <div style={{ width: 300, flexShrink: 0 }}>
          <NodeInspector
            node={selected}
            onChange={patchSelected}
            onDelete={() => selectedId && deleteNode(selectedId)}
          />
        </div>
      </div>
    </div>
  );
}
