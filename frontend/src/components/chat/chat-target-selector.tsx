/* Target selector: a segmented Agent|Workflow toggle plus a custom dropdown of
 * the matching list. Styled with the app's token system (no native <select>
 * chrome). Vertical, full-width — sized for the new-chat modal.
 */

import { useEffect, useRef, useState } from "react";
import { Bot, Workflow as WorkflowIcon, ChevronDown, Check } from "lucide-react";
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

const SEGMENTS: { key: TargetType; label: string; Icon: typeof Bot }[] = [
  { key: "agent", label: "Agent", Icon: Bot },
  { key: "workflow", label: "Workflow", Icon: WorkflowIcon },
];

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
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const selected =
    targetType === mode ? list.find((x) => x.id === targetId) ?? null : null;
  const listDisabled = disabled || loading || list.length === 0;

  // Close the dropdown on outside click / Escape.
  useEffect(() => {
    if (!open) return;
    function onDoc(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function pickMode(next: TargetType) {
    if (next === mode) return;
    setOpen(false);
    onChange(next, "", ""); // reset the selection when switching mode
  }

  const ItemIcon = mode === "agent" ? Bot : WorkflowIcon;

  return (
    <div
      ref={rootRef}
      style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", width: "100%" }}
    >
      {/* Segmented control */}
      <div
        role="tablist"
        aria-label="Chat target type"
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "4px",
          padding: "4px",
          borderRadius: "var(--radius-control, 10px)",
          background: "var(--color-surface-muted)",
          border: "1px solid var(--color-border)",
        }}
      >
        {SEGMENTS.map(({ key, label, Icon }) => {
          const active = mode === key;
          return (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={active}
              disabled={disabled}
              onClick={() => pickMode(key)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "var(--space-2)",
                padding: "var(--space-2) var(--space-3)",
                borderRadius: "var(--radius-control, 8px)",
                border: "none",
                background: active ? "var(--color-surface)" : "transparent",
                color: active ? "var(--color-primary)" : "var(--color-text-secondary)",
                boxShadow: active ? "var(--shadow-sm, 0 1px 2px rgba(0,0,0,0.08))" : "none",
                cursor: disabled ? "not-allowed" : "pointer",
                fontSize: "var(--text-body)",
                fontWeight: active ? 600 : 500,
                transition: "background 150ms ease-out, color 150ms ease-out",
              }}
            >
              <Icon size={16} strokeWidth={1.75} />
              {label}
            </button>
          );
        })}
      </div>

      {/* Custom dropdown */}
      <div style={{ position: "relative" }}>
        <button
          type="button"
          disabled={listDisabled}
          aria-haspopup="listbox"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--space-2)",
            padding: "var(--space-2) var(--space-3)",
            borderRadius: "var(--radius-control, 8px)",
            border: `1px solid ${open ? "var(--color-primary)" : "var(--color-border)"}`,
            background: "var(--color-surface)",
            color: selected ? "var(--color-text-primary)" : "var(--color-text-tertiary)",
            cursor: listDisabled ? "not-allowed" : "pointer",
            fontSize: "var(--text-body)",
            opacity: listDisabled ? 0.7 : 1,
            transition: "border-color 150ms ease-out",
          }}
        >
          <span style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-2)", overflow: "hidden" }}>
            {selected && <ItemIcon size={15} strokeWidth={1.5} style={{ flexShrink: 0, opacity: 0.8 }} />}
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {selected ? selected.name : mode === "agent" ? "Select an agent" : "Select a workflow"}
            </span>
          </span>
          <ChevronDown
            size={16}
            strokeWidth={1.75}
            style={{
              flexShrink: 0,
              transform: open ? "rotate(180deg)" : "none",
              transition: "transform 150ms ease-out",
            }}
          />
        </button>

        {open && !listDisabled && (
          <ul
            role="listbox"
            style={{
              position: "absolute",
              top: "calc(100% + 4px)",
              left: 0,
              right: 0,
              zIndex: 20,
              margin: 0,
              padding: "var(--space-1)",
              listStyle: "none",
              maxHeight: "220px",
              overflowY: "auto",
              borderRadius: "var(--radius-control, 8px)",
              border: "1px solid var(--color-border)",
              background: "var(--color-surface)",
              boxShadow: "var(--shadow-md, 0 8px 24px rgba(0,0,0,0.14))",
            }}
          >
            {list.map((item) => {
              const isSel = item.id === selected?.id;
              return (
                <li key={item.id} role="option" aria-selected={isSel}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange(mode, item.id, item.name);
                      setOpen(false);
                    }}
                    onMouseEnter={(e) => {
                      if (!isSel) e.currentTarget.style.background = "var(--color-surface-muted)";
                    }}
                    onMouseLeave={(e) => {
                      if (!isSel) e.currentTarget.style.background = "transparent";
                    }}
                    style={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      gap: "var(--space-2)",
                      padding: "var(--space-2) var(--space-3)",
                      borderRadius: "var(--radius-control, 6px)",
                      border: "none",
                      background: isSel ? "var(--color-primary-soft)" : "transparent",
                      color: isSel ? "var(--color-primary)" : "var(--color-text-primary)",
                      cursor: "pointer",
                      fontSize: "var(--text-body)",
                      textAlign: "left",
                      transition: "background 120ms ease-out",
                    }}
                  >
                    <ItemIcon size={15} strokeWidth={1.5} style={{ flexShrink: 0, opacity: 0.8 }} />
                    <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {item.name}
                    </span>
                    {isSel && <Check size={15} strokeWidth={2} style={{ flexShrink: 0 }} />}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {!loading && list.length === 0 && (
        <span className="text-caption" style={{ color: "var(--color-text-tertiary)" }}>
          {mode === "agent" ? "No agents" : "No workflows"} — sign in required
        </span>
      )}
    </div>
  );
}
