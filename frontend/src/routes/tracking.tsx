/* /tracking — per-account realtime review inbox. */
import TrackingList from "../components/tracking/TrackingList";

export default function TrackingPage() {
  return (
    <div data-testid="vaic-tracking-page" style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <h1 className="text-h1">Tracking</h1>
      <p style={{ color: "var(--color-text-muted)", marginTop: "calc(-1 * var(--space-2))" }}>
        Tiến độ realtime của các quy trình đang chờ bạn xử lý.
      </p>
      <TrackingList />
    </div>
  );
}
