/* Actions — personnel picker for "notify users". A name/department search box
 * over a scrollable list of checkbox rows (person icon + derived name + dim
 * department badge). Replaces the raw comma-separated user-id input. Selection
 * toggles ids in `selected`. Users expose no real name field, so the display
 * name is derived from the email local-part (shared `displayName`); search
 * matches the derived name, the email, OR the department name. */

import { useMemo, useState } from "react";
import { User } from "lucide-react";
import { useUsers } from "../../hooks/useUsers";
import { useDepartments } from "../../hooks/useDepartments";
import { displayName } from "../../lib/userDisplay";

interface Props {
  selected: string[];
  onChange: (ids: string[]) => void;
}

export default function NotifyUserPicker({ selected, onChange }: Props) {
  const users = useUsers();
  const departments = useDepartments();
  const [query, setQuery] = useState("");

  const roster = users.data ?? [];

  // department_id -> department name (fallback: empty string when unknown).
  const deptName = useMemo(() => {
    const map = new Map<string, string>();
    for (const d of departments.data ?? []) map.set(d.id, d.name);
    return (id: string | null): string => (id ? map.get(id) ?? "" : "");
  }, [departments.data]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return roster;
    return roster.filter((u) => {
      const name = displayName(u.email).toLowerCase();
      const email = u.email.toLowerCase();
      const dept = deptName(u.department_id).toLowerCase();
      return name.includes(q) || email.includes(q) || dept.includes(q);
    });
  }, [roster, query, deptName]);

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
        placeholder="Tìm nhân sự theo tên hoặc phòng ban…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div
        style={{
          maxHeight: 220,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          border: "1px solid var(--color-border)",
          borderRadius: 6,
        }}
      >
        {filtered.length === 0 && (
          <div style={{ padding: "var(--space-2)", fontSize: 12, opacity: 0.6 }}>
            Không tìm thấy nhân sự nào.
          </div>
        )}
        {filtered.map((u) => {
          const checked = selected.includes(u.id);
          const dept = deptName(u.department_id);
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
              <span style={{ minWidth: 0, flex: 1, display: "flex", flexDirection: "column", lineHeight: 1.25 }}>
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
              {dept && (
                <span
                  style={{
                    flexShrink: 0,
                    fontSize: 11,
                    padding: "2px 8px",
                    borderRadius: 999,
                    background: "var(--color-surface-2, #F1F5F9)",
                    color: "var(--color-text-muted, #64748B)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {dept}
                </span>
              )}
            </label>
          );
        })}
      </div>
      <span style={{ fontSize: 11, opacity: 0.7 }}>
        {selected.length > 0
          ? `${selected.length} người sẽ được thông báo`
          : "Chưa chọn — mặc định báo chủ action"}
      </span>
    </div>
  );
}
