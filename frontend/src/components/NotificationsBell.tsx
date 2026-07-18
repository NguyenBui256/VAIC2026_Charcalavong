/* Notifications bell for the Topbar. Polls GET /notifications (10s), shows the
 * unread count as a badge, and a click-to-open dropdown listing recent alerts
 * with mark-read / mark-all-read. */
import { useState } from "react";
import { Bell } from "lucide-react";
import { useNotifications, useNotificationMutations } from "../hooks/useNotifications";

export default function NotificationsBell() {
  const { data } = useNotifications();
  const { markRead, markAllRead } = useNotificationMutations();
  const [open, setOpen] = useState(false);

  const items = data ?? [];
  const unread = items.filter((n) => n.read_at === null).length;

  return (
    <div style={{ position: "relative" }}>
      <button
        type="button"
        className="vaic-focusable"
        aria-label="Notifications"
        title="Notifications"
        onClick={() => setOpen((v) => !v)}
        style={{
          position: "relative", background: "none", border: "none",
          cursor: "pointer", color: "var(--color-text-secondary)",
          display: "inline-flex", alignItems: "center", padding: "var(--space-1)",
        }}
      >
        <Bell size={18} strokeWidth={1.5} aria-hidden="true" />
        {unread > 0 && (
          <span
            style={{
              position: "absolute", top: -4, right: -4, minWidth: 16, height: 16,
              padding: "0 4px", borderRadius: 8, background: "var(--color-error)",
              color: "#fff", fontSize: 10, lineHeight: "16px", textAlign: "center",
            }}
          >
            {unread}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          style={{
            position: "absolute", right: 0, top: "calc(100% + 8px)", width: 340,
            maxHeight: 420, overflowY: "auto", zIndex: 60,
            background: "var(--color-surface)", border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-card)", boxShadow: "var(--shadow-md)",
            padding: "var(--space-2)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)" }}>
            <strong style={{ fontSize: "var(--text-small)" }}>Notifications</strong>
            <button
              type="button" className="vaic-focusable"
              onClick={() => markAllRead.mutate()}
              disabled={unread === 0 || markAllRead.isPending}
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--color-primary)", fontSize: "var(--text-small)" }}
            >
              Mark all read
            </button>
          </div>

          {items.length === 0 ? (
            <p style={{ color: "var(--color-text-tertiary)", fontSize: "var(--text-small)", padding: "var(--space-2)" }}>
              No notifications yet.
            </p>
          ) : (
            items.map((n) => (
              <button
                key={n.id}
                type="button"
                className="vaic-focusable"
                onClick={() => n.read_at === null && markRead.mutate(n.id)}
                style={{
                  display: "block", width: "100%", textAlign: "left", cursor: "pointer",
                  background: n.read_at === null ? "var(--color-primary-soft)" : "transparent",
                  border: "none", borderRadius: "var(--radius-control)",
                  padding: "var(--space-2)", marginBottom: "var(--space-1)",
                }}
              >
                <div style={{ fontSize: "var(--text-small)", fontWeight: n.read_at === null ? 600 : 400, color: "var(--color-text)" }}>
                  {n.title}
                </div>
                {n.body && (
                  <div style={{ fontSize: "11px", color: "var(--color-text-secondary)" }}>{n.body}</div>
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
