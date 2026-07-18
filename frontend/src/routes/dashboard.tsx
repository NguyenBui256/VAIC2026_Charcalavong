/* Story 1.10 — Dashboard surface (UX-DR15).
 *
 * Three sections: KPI strip, Escalation inbox preview, Recent Runs list.
 * Data comes from useDashboardData() (TanStack Query + mock); real wiring
 * arrives in Epics 3, 5, 6. Loading / empty / error states follow UX-DR23.
 */

import type { CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import KpiStrip from "../components/dashboard/KpiStrip";
import EscalationInbox from "../components/dashboard/EscalationInbox";
import RecentRuns from "../components/dashboard/RecentRuns";
import { useDashboardData } from "../hooks/useDashboardData";

export default function DashboardPage() {
  const { query, data, isLoading, isError } = useDashboardData();
  const navigate = useNavigate();

  const pageStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: "var(--space-5)",
  };

  const headerStyle: CSSProperties = {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: "var(--space-3)",
  };

  const columnsStyle: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
    gap: "var(--space-4)",
  };

  const errorMessage = isError
    ? (query.error?.message ?? "Failed to load dashboard")
    : null;

  const handleRetry = () => {
    void query.refetch();
  };

  // Click-to-trace: navigate to the trace view for the run.
  // `/audit` reads the `run_id` query param to pre-fill its Run filter.
  const handleOpenRun = (runId: string) => {
    navigate(`/audit?run_id=${runId}`);
  };

  return (
    <div style={pageStyle} data-testid="vaic-dashboard">
      <header style={headerStyle}>
        <div>
          <h1
            className="text-h1"
            style={{ marginBottom: "var(--space-1)", color: "var(--color-text)" }}
          >
            Dashboard
          </h1>
          <p
            className="text-body"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            What&apos;s running, what needs your attention, what ran recently.
          </p>
        </div>
      </header>

      <KpiStrip
        data={data?.kpis}
        loading={isLoading}
        error={errorMessage}
        onRetry={handleRetry}
      />

      <div style={columnsStyle}>
        <EscalationInbox
          items={data?.escalations ?? []}
          loading={isLoading}
          error={errorMessage}
          onRetry={handleRetry}
          onOpen={handleOpenRun}
        />
        <RecentRuns
          runs={data?.recentRuns ?? []}
          loading={isLoading}
          error={errorMessage}
          onRetry={handleRetry}
          onOpenRun={handleOpenRun}
        />
      </div>
    </div>
  );
}
