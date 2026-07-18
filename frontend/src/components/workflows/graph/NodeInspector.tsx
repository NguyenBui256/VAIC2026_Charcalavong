/* 3D — right panel: edit the selected node (label, key, agent, approvers). */
import { useAgents } from "../../../hooks/useAgents";
import { useUsers } from "../../../hooks/useUsers";
import { Button } from "../../ui";
import type { Node } from "@xyflow/react";
import type { RFNodeData } from "../../../lib/graphEditorState";

export interface NodeInspectorProps {
  node: Node<RFNodeData> | null;
  onChange: (patch: Partial<RFNodeData>) => void;
  onDelete: () => void;
}

export default function NodeInspector({ node, onChange, onDelete }: NodeInspectorProps) {
  const agents = useAgents({});
  const users = useUsers();
  if (!node) {
    return <div style={{ opacity: 0.6 }}>Select a node to edit, or add one.</div>;
  }
  const d = node.data;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <label className="vaic-form-label">Label</label>
      <input
        className="vaic-form-input vaic-focusable"
        value={d.label}
        onChange={(e) => onChange({ label: e.target.value })}
      />
      <label className="vaic-form-label">Node key</label>
      <input
        className="vaic-form-input vaic-focusable"
        value={d.nodeKey}
        onChange={(e) => onChange({ nodeKey: e.target.value })}
      />
      <label className="vaic-form-label">Agent</label>
      <select
        className="vaic-form-input vaic-focusable"
        value={d.agentId}
        onChange={(e) => onChange({ agentId: e.target.value })}
      >
        <option value="">— choose agent —</option>
        {(agents.data ?? []).map((a) => (
          <option key={a.id} value={a.id}>{a.name}</option>
        ))}
      </select>
      <label className="vaic-form-label">Approvers (none = auto)</label>
      <select
        multiple
        className="vaic-form-input vaic-focusable"
        value={d.approverUserIds}
        onChange={(e) =>
          onChange({
            approverUserIds: Array.from(e.target.selectedOptions, (o) => o.value),
          })
        }
      >
        {(users.data ?? []).map((u) => (
          <option key={u.id} value={u.id}>{u.email}</option>
        ))}
      </select>
      <Button variant="ghost" onClick={onDelete}>Delete node</Button>
    </div>
  );
}
