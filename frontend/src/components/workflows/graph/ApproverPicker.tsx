/* 3D — node approver picker: a name/email search box over a scrollable list of
 * checkbox rows (person icon + short name + dim email). Replaces the raw
 * <select multiple> of emails. Selection toggles ids in approverUserIds. */

import { useMemo, useState } from "react";
import { User } from "lucide-react";
import { useUsers } from "../../../hooks/useUsers";
import { displayName, matchesUser } from "../../../lib/userDisplay";

interface Props {
  selected: string[];
  onChange: (ids: string[]) => void;
}

export default function ApproverPicker({ selected, onChange }: Props) {
  const users = useUsers();
  const [query, setQuery] = useState("");

  const roster = users.data ?? [];
  const filtered = useMemo(
    () => roster.filter((u) => matchesUser(u, query)),
    [roster, query],
  );

  function toggle(id: string) {
    onChange(
      selected.includes(id)
        ? selected.filter((x) => x !== id)
        : [...selected, id],
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <input
        className="vaic-form-input vaic-focusable"
        placeholder="Tìm người theo tên hoặc email…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div
        style={{
          maxHeight: 200,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          border: "1px solid var(--color-border)",
          borderRadius: 6,
        }}
      >
        {filtered.length === 0 && (
          <div style={{ padding: "var(--space-2)", fontSize: 12, opacity: 0.6 }}>
            Không tìm thấy người nào.
          </div>
        )}
        {filtered.map((u) => {
          const checked = selected.includes(u.id);
          return (
            <label
              key={u.id}
              className="vaic-focusable"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-2)",
                padding: "6px 8px",
                cursor: "pointer",
                background: checked ? "var(--color-primary-soft, #EEF2FF)" : "transparent",
              }}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggle(u.id)}
                style={{ flexShrink: 0 }}
              />
              <User size={15} strokeWidth={1.75} style={{ flexShrink: 0, opacity: 0.7 }} />
              <span style={{ minWidth: 0, display: "flex", flexDirection: "column", lineHeight: 1.25 }}>
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: 500,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {displayName(u.email)}
                </span>
                <span
                  style={{
                    fontSize: 11,
                    opacity: 0.6,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                >
                  {u.email}
                </span>
              </span>
            </label>
          );
        })}
      </div>
      <span style={{ fontSize: 11, opacity: 0.7 }}>
        {selected.length > 0
          ? `${selected.length} người duyệt`
          : "Chưa chọn — tự động (auto)"}
      </span>
    </div>
  );
}
