/* Header control: pick chat target (agent or workflow) for the active
 * conversation. Segmented Agent|Workflow toggle + a native <select> of
 * the corresponding list (real data via useChatTargets).
 */

import type { ChatTargetOption } from "../../lib/chatTargets";

type TargetType = "agent" | "workflow";

interface Props {
  targetType: TargetType | null;
  targetId: string | null;
  agents: ChatTargetOption[];
  workflows: ChatTargetOption[];
  loading: boolean;
  disabled?: boolean;
  onChange: (type: TargetType, id: string, name: string) => void;
}

export default function ChatTargetSelector({
  targetType,
  targetId,
  agents,
  workflows,
  loading,
  disabled,
  onChange,
}: Props) {
  const mode: TargetType = targetType ?? "agent";
  const list = mode === "agent" ? agents : workflows;

  function segButtonStyle(active: boolean) {
    return {
      padding: "var(--space-1) var(--space-3)",
      borderRadius: "var(--radius-control, 6px)",
      border: "1px solid var(--color-border)",
      background: active ? "var(--color-primary-soft)" : "var(--color-surface)",
      color: active ? "var(--color-primary)" : "var(--color-text-secondary)",
      cursor: disabled ? "not-allowed" : "pointer",
      fontSize: "var(--text-caption)",
      fontWeight: 500,
    } as const;
  }

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
      <div style={{ display: "flex", gap: "var(--space-1)" }}>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange("agent", "", "")}
          style={segButtonStyle(mode === "agent")}
        >
          Agent
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange("workflow", "", "")}
          style={segButtonStyle(mode === "workflow")}
        >
          Workflow
        </button>
      </div>

      <select
        disabled={disabled || loading || list.length === 0}
        value={targetType === mode ? targetId ?? "" : ""}
        onChange={(e) => {
          const id = e.target.value;
          const item = list.find((x) => x.id === id);
          if (item) onChange(mode, item.id, item.name);
        }}
        style={{
          padding: "var(--space-1) var(--space-2)",
          borderRadius: "var(--radius-control, 6px)",
          border: "1px solid var(--color-border)",
          background: "var(--color-surface)",
          color: "var(--color-text-primary)",
          fontSize: "var(--text-caption)",
          maxWidth: "220px",
        }}
      >
        <option value="" disabled>
          {mode === "agent" ? "Chọn agent…" : "Chọn workflow…"}
        </option>
        {list.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name}
          </option>
        ))}
      </select>

      {!loading && list.length === 0 && (
        <span
          className="text-caption"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          {mode === "agent" ? "Không có agent" : "Không có workflow"} — cần đăng nhập
        </span>
      )}
    </div>
  );
}
