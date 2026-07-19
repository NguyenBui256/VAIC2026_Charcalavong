/* 3D — right panel: edit the selected node (label, key, agent, I/O notes,
 * approvers). I/O notes live in node.config; approvers use a searchable
 * checkbox picker. */
import { useAgents } from "../../../hooks/useAgents";
import { Button } from "../../ui";
import type { Node } from "@xyflow/react";
import type { RFNodeData } from "../../../lib/graphEditorState";
import ApproverPicker from "./ApproverPicker";

export interface NodeInspectorProps {
  node: Node<RFNodeData> | null;
  onChange: (patch: Partial<RFNodeData>) => void;
  onDelete: () => void;
}

export default function NodeInspector({ node, onChange, onDelete }: NodeInspectorProps) {
  const agents = useAgents({});
  if (!node) {
    return <div style={{ opacity: 0.6 }}>Select a node to edit, or add one.</div>;
  }
  const d = node.data;
  const config = d.config ?? {};
  const inputDesc = typeof config.input_description === "string" ? config.input_description : "";
  const outputDesc = typeof config.output_description === "string" ? config.output_description : "";

  function patchConfig(patch: Record<string, unknown>) {
    onChange({ config: { ...config, ...patch } });
  }

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

      <label className="vaic-form-label">Mô tả đầu vào</label>
      <textarea
        className="vaic-form-input vaic-focusable"
        rows={3}
        placeholder="Node này nhận đầu vào gì? (dữ liệu, ngữ cảnh…)"
        value={inputDesc}
        onChange={(e) => patchConfig({ input_description: e.target.value })}
        style={{ resize: "vertical", fontFamily: "inherit" }}
      />
      <label className="vaic-form-label">Đầu ra mong muốn</label>
      <textarea
        className="vaic-form-input vaic-focusable"
        rows={3}
        placeholder="Kết quả mong muốn tại node này là gì?"
        value={outputDesc}
        onChange={(e) => patchConfig({ output_description: e.target.value })}
        style={{ resize: "vertical", fontFamily: "inherit" }}
      />

      <label className="vaic-form-label">Người duyệt (không chọn = auto)</label>
      <ApproverPicker
        selected={d.approverUserIds}
        onChange={(ids) => onChange({ approverUserIds: ids })}
      />

      <Button variant="ghost" onClick={onDelete}>Delete node</Button>
    </div>
  );
}
