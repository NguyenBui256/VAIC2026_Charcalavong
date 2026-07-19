/* Tracking inbox list: scope toggle (active/all), polled via useTrackingList,
 * renders a TrackingRow per session with loading/error/empty states.
 */
import { useState } from "react";
import { Button, ErrorState, Skeleton } from "../ui";
import TrackingRow from "./TrackingRow";
import { useTrackingList } from "../../hooks/useTracking";

export default function TrackingList() {
  const [scope, setScope] = useState<"active" | "all">("active");
  const query = useTrackingList(scope);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <div role="tablist" aria-label="Phạm vi" style={{ display: "flex", gap: "var(--space-1)" }}>
        <Button
          variant={scope === "active" ? "primary" : "ghost"}
          onClick={() => setScope("active")}
          aria-pressed={scope === "active"}
        >
          Đang hoạt động
        </Button>
        <Button
          variant={scope === "all" ? "primary" : "ghost"}
          onClick={() => setScope("all")}
          aria-pressed={scope === "all"}
        >
          Tất cả
        </Button>
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
