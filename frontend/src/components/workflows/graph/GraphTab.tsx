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
import GraphToolbar from "./GraphToolbar";
import PaletteSidebar, { type EdgeMode } from "./PaletteSidebar";
import GraphRightPanel from "./GraphRightPanel";
import { GraphUsersProvider } from "./GraphUsersContext";
import { useWorkflowGraph } from "../../../hooks/useWorkflowGraph";
import { useWorkflowGraphMutation } from "../../../hooks/useWorkflowGraphMutation";
import { useUsers } from "../../../hooks/useUsers";
import { useAgents } from "../../../hooks/useAgents";
import { useGraphChat } from "../../../hooks/useGraphChat";
import type { GraphCommand } from "../../../lib/graphChatCommands";
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
  const agents = useAgents({});

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

  function resetGraph() {
    if (!graph.data) return;
    const rf = toReactFlow(graph.data);
    setNodes(allPositionsZero(rf.nodes) ? layoutVertical(rf.nodes, rf.edges) : rf.nodes);
    setEdges(rf.edges);
    setDirty(false);
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

  // Resolve a chat node reference (by node key first, then case-insensitive label).
  function findNode(ref: string): Node<RFNodeData> | undefined {
    const byKey = nodes.find((n) => n.data.nodeKey === ref);
    if (byKey) return byKey;
    const low = ref.toLowerCase();
    return nodes.find((n) => n.data.label.toLowerCase() === low);
  }

  function runChatCommand(cmd: GraphCommand): string {
    switch (cmd.kind) {
      case "help":
        return [
          "Commands:",
          "• add node <label>",
          "• set agent <agent> on <node>  (or: gán agent <agent> cho <node>)",
          "• connect <A> -> <B>  (or: nối <A> -> <B>)",
          "• delete node <node>  (or: xoá node <node>)",
          "• list",
        ].join("\n");
      case "list": {
        if (nodes.length === 0) return "No nodes yet.";
        const lines = nodes.map((n) => {
          const agent = (agents.data ?? []).find((a) => a.id === n.data.agentId);
          return `• ${n.data.nodeKey} — ${n.data.label}${agent ? ` (${agent.name})` : " (no agent)"}`;
        });
        return `${lines.join("\n")}\n${edges.length} edge(s).`;
      }
      case "add_node": {
        const key = nextNodeKey(nodes.map((n) => n.data.nodeKey));
        setNodes((ns) => [
          ...ns,
          {
            id: key,
            type: "agent",
            position: { x: 80 + ns.length * 40, y: 80 + ns.length * 40 },
            data: { label: cmd.label, agentId: "", nodeKey: key, approverUserIds: [] },
          },
        ]);
        setSelectedId(key);
        setDirty(true);
        return `Added node "${cmd.label}" (${key}).`;
      }
      case "assign_agent": {
        const node = findNode(cmd.nodeRef);
        if (!node) return `Node "${cmd.nodeRef}" not found.`;
        const low = cmd.agentName.toLowerCase();
        const matches = (agents.data ?? []).filter((a) => a.name.toLowerCase().includes(low));
        if (matches.length === 0) return `Agent "${cmd.agentName}" not found.`;
        if (matches.length > 1) return `"${cmd.agentName}" matches ${matches.length} agents — be more specific.`;
        const agent = matches[0];
        setNodes((ns) => ns.map((n) => (n.id === node.id ? { ...n, data: { ...n.data, agentId: agent.id } } : n)));
        setDirty(true);
        return `Assigned agent "${agent.name}" to "${node.data.label}".`;
      }
      case "connect": {
        const from = findNode(cmd.from);
        const to = findNode(cmd.to);
        if (!from) return `Node "${cmd.from}" not found.`;
        if (!to) return `Node "${cmd.to}" not found.`;
        if (from.id === to.id) return "Cannot connect a node to itself.";
        const dup = edges.some((e) => e.source === from.id && e.target === to.id);
        if (dup) return `Edge ${from.data.label} -> ${to.data.label} already exists.`;
        setEdges((es) =>
          addEdge({ id: `${from.id}->${to.id}`, source: from.id, target: to.id }, es),
        );
        setDirty(true);
        return `Connected ${from.data.label} -> ${to.data.label}.`;
      }
      case "delete_node": {
        const node = findNode(cmd.nodeRef);
        if (!node) return `Node "${cmd.nodeRef}" not found.`;
        deleteNode(node.id);
        return `Deleted node "${node.data.label}".`;
      }
      default:
        return 'Unrecognized command. Type "help" for the list.';
    }
  }

  // Live authoring path: the backend/provider validates and auto-applies the full graph.
  // The deterministic parser above is retained temporarily for compatibility tests only.
  void runChatCommand;
  const chat = useGraphChat(workflowId);

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
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-3)",
        // Fill the space below the shell header + tab bar. Tune the offset to
        // the running shell if the toolbar/header height changes.
        height: "calc(100vh - 240px)",
        minHeight: 480,
      }}
    >
      <GraphToolbar
        onAddNode={addNode}
        onDeleteSelected={() => selectedId && deleteNode(selectedId)}
        onSave={save}
        onReset={resetGraph}
        saving={isPending}
        dirty={dirty}
        error={error}
      />
      <div
        style={{
          display: "flex",
          gap: "var(--space-4)",
          alignItems: "stretch",
          flex: 1,
          minHeight: 0,
        }}
      >
        <PaletteSidebar
          edgeMode={edgeMode}
          onEdgeModeChange={setEdgeMode}
          onAutoLayout={autoLayout}
        />
        <div style={{ flex: 1, minWidth: 0, minHeight: 0 }}>
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
        <GraphRightPanel
          inspector={{
            node: selected,
            onChange: patchSelected,
            onDelete: () => selectedId && deleteNode(selectedId),
          }}
          chat={{
            messages: chat.messages,
            onSend: chat.send,
            pending: chat.pending,
            providers: chat.models,
            session: chat.session,
            onModelChange: chat.changeModel,
            onUndo: chat.undo,
            error: chat.error ? (chat.error as Error).message : undefined,
          }}
        />
      </div>
    </div>
  );
}
