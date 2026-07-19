/* Frontend-only: compact approver display for a graph node — up to two chips,
 * each a person icon + short (email-derived) name, plus a "+N" overflow. Full
 * "name — email" list on hover via Tooltip. */

import { User } from "lucide-react";
import { Tooltip } from "../../ui";
import { useGraphUsers } from "./GraphUsersContext";
import { displayName } from "../../../lib/userDisplay";

export default function ApproverAvatars({ userIds }: { userIds: string[] }) {
  const users = useGraphUsers();
  if (userIds.length === 0) return null;

  const resolved = userIds.map((id) => {
    const email = users.get(id)?.email ?? id;
    return { email, name: displayName(email) };
  });
  const shown = resolved.slice(0, 2);
  const overflow = resolved.length - shown.length;
  const tooltip = resolved.map((u) => `${u.name} — ${u.email}`).join(", ");

  return (
    <Tooltip label={`Người duyệt: ${tooltip}`}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
        {shown.map((u, i) => (
          <span
            key={userIds[i]}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 3,
              maxWidth: 82,
              padding: "1px 6px 1px 4px",
              borderRadius: 999,
              background: "var(--color-warning-soft, #FEF3C7)",
              color: "var(--color-warning, #b45309)",
              fontSize: 10,
              fontWeight: 600,
            }}
          >
            <User size={11} strokeWidth={2} style={{ flexShrink: 0 }} />
            <span
              style={{
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {u.name}
            </span>
          </span>
        ))}
        {overflow > 0 && (
          <span style={{ fontSize: 10, opacity: 0.8 }}>+{overflow}</span>
        )}
      </span>
    </Tooltip>
  );
}
