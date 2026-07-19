/* Tracking inbox list: scope toggle (active/all), polled via useTrackingList,
 * renders a TrackingRow per session with loading/error/empty states.
 */
import { useState } from "react";
import { ErrorState, Skeleton } from "../ui";
import TrackingRow from "./TrackingRow";
import { useTrackingList } from "../../hooks/useTracking";

export default function TrackingList() {
  const [scope, setScope] = useState<"active" | "all">("active");
  const query = useTrackingList(scope);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <button
          type="button"
          onClick={() => setScope("active")}
          aria-pressed={scope === "active"}
          style={{ fontWeight: scope === "active" ? 700 : 400 }}
        >
          Đang hoạt động
        </button>
        <button
          type="button"
          onClick={() => setScope("all")}
          aria-pressed={scope === "all"}
          style={{ fontWeight: scope === "all" ? 700 : 400 }}
        >
          Tất cả
        </button>
      </div>

      {query.isLoading && <Skeleton lines={4} height="56px" />}
      {query.isError && (
        <ErrorState message={query.error?.message ?? "Không tải được Tracking"} />
      )}
      {query.data && query.data.length === 0 && (
        <div style={{ color: "var(--color-text-muted)", padding: "var(--space-4)" }}>
          Chưa có session nào cần bạn theo dõi.
        </div>
      )}
      {query.data?.map((item) => (
        <TrackingRow key={item.run_id} item={item} />
      ))}
    </div>
  );
}
