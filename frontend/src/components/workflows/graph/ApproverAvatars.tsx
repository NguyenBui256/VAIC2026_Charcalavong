/* Frontend-only: compact approver display for a graph node — up to two
 * initials chips + "+N" overflow, full email list on hover via Tooltip. */

import { Tooltip } from "../../ui";
import { useGraphUsers } from "./GraphUsersContext";

function initials(email: string): string {
  const name = email.split("@")[0] ?? email;
  const parts = name.split(/[._-]+/).filter(Boolean);
  const chars = parts.length >= 2 ? parts[0][0] + parts[1][0] : name.slice(0, 2);
  return chars.toUpperCase();
}

export default function ApproverAvatars({ userIds }: { userIds: string[] }) {
  const users = useGraphUsers();
  if (userIds.length === 0) return null;
  const resolved = userIds.map((id) => users.get(id));
  const emails = resolved.map((u, i) => u?.email ?? userIds[i]);
  const shown = userIds.slice(0, 2);
  const overflow = userIds.length - shown.length;

  return (
    <Tooltip label={`Approvers: ${emails.join(", ")}`}>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 2 }}>
        {shown.map((id, i) => (
          <span
            key={id}
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 18,
              height: 18,
              borderRadius: "50%",
              background: "var(--color-warning, #b45309)",
              color: "#fff",
              fontSize: 9,
              fontWeight: 600,
            }}
          >
            {initials(emails[i])}
          </span>
        ))}
        {overflow > 0 && (
          <span style={{ fontSize: 10, opacity: 0.8 }}>+{overflow}</span>
        )}
      </span>
    </Tooltip>
  );
}
