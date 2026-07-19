/* One session row in the Tracking inbox. Clicking navigates to the existing
 * RunTrackingView, where Approve/Reject/Retry live.
 */
import { useNavigate } from "react-router-dom";
import RunStatusBadge from "../workflows/runs/RunStatusBadge";
import type { TrackingItem } from "../../lib/trackingApi";

export interface TrackingRowProps {
  item: TrackingItem;
}

export default function TrackingRow({ item }: TrackingRowProps) {
  const navigate = useNavigate();
  const go = () =>
    navigate(`/workflows/${item.workflow_id}/runs/${item.run_id}`);

  return (
    <button
      type="button"
      data-testid="vaic-tracking-row"
      onClick={go}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-3)",
        width: "100%",
        textAlign: "left",
        padding: "var(--space-3)",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-card, 8px)",
        background: item.is_my_turn
          ? "var(--color-warning-bg, rgba(255,193,7,0.08))"
          : "var(--color-surface, transparent)",
        cursor: "pointer",
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <strong>{item.workflow_name || "Workflow"}</strong>
          {item.is_my_turn && (
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 600,
                padding: "2px 8px",
                borderRadius: "999px",
                background: "var(--color-warning, #b8860b)",
                color: "#fff",
              }}
            >
              Đến lượt bạn
            </span>
          )}
        </div>
        <div style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
          {item.current_node
            ? `Đang ở bước: ${item.current_node.label}`
            : "Chưa có bước đang chạy"}
        </div>
      </div>
      <RunStatusBadge status={item.run_status} />
    </button>
  );
}
