/* Story 1.8 — Dashboard placeholder.
 * Real dashboard surface arrives in Story 1.10.
 */

const containerStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  minHeight: "60vh",
  textAlign: "center",
};

export default function DashboardPage() {
  return (
    <div style={containerStyle} data-testid="vaic-dashboard">
      <h1 className="text-h1" style={{ marginBottom: "var(--space-2)" }}>
        Dashboard
      </h1>
      <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
        Dashboard coming in Story 1.10
      </p>
    </div>
  );
}
