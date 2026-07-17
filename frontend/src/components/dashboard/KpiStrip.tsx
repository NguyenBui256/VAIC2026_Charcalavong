/* Story 1.10 — KPI strip (UX-DR15).
 *
 * Three cards: Active Runs, Pending Escalations, Today's Mini-App Events.
 * Numbers use tabular-nums (platform-design.md §3.1).
 * Loading / error states follow UX-DR23.
 */

import type { CSSProperties, ReactNode } from "react";
import { Card, Skeleton, ErrorState } from "../ui";
import { ICON_STROKE_WIDTH, semanticIcons } from "../../lib/icons";
import type { KpiCounts } from "../../lib/mockData";

export interface KpiStripProps {
  data?: KpiCounts;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

const RunIcon = semanticIcons.Run;
const EscalationIcon = semanticIcons.Escalation;
const MiniAppIcon = semanticIcons.MiniApp;

const valueStyle: CSSProperties = {
  fontVariantNumeric: "tabular-nums",
  fontSize: "32px",
  fontWeight: 600,
  color: "var(--color-text)",
  lineHeight: 1.2,
  display: "block",
};

const labelStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "var(--space-1)",
  color: "var(--color-text-tertiary)",
};

function KpiCard({
  testId,
  label,
  value,
  icon,
}: {
  testId: string;
  label: string;
  value: ReactNode;
  icon: ReactNode;
}) {
  return (
    <Card>
      <span
        className="vaic-kpi-value"
        data-testid={testId}
        style={valueStyle}
      >
        {typeof value === "number" ? String(value) : value}
      </span>
      <span className="text-small" style={labelStyle}>
        {icon}
        {label}
      </span>
    </Card>
  );
}

function KpiCardSkeleton() {
  return (
    <Card>
      <Skeleton width="60px" height="32px" />
      <div style={{ marginTop: "var(--space-2)" }}>
        <Skeleton width="120px" height="14px" />
      </div>
    </Card>
  );
}

export default function KpiStrip({
  data,
  loading = false,
  error = null,
  onRetry,
}: KpiStripProps) {
  const wrapperStyle: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
    gap: "var(--space-3)",
  };

  if (error) {
    return (
      <section data-testid="kpi-strip" style={wrapperStyle}>
        <Card>
          <ErrorState
            message={error}
            retry={
              onRetry ? (
                <button
                  className="vaic-btn vaic-btn-secondary vaic-focusable"
                  onClick={onRetry}
                >
                  Retry
                </button>
              ) : undefined
            }
          />
        </Card>
      </section>
    );
  }

  if (loading || !data) {
    return (
      <section data-testid="kpi-strip" style={wrapperStyle}>
        <KpiCardSkeleton />
        <KpiCardSkeleton />
        <KpiCardSkeleton />
      </section>
    );
  }

  return (
    <section data-testid="kpi-strip" style={wrapperStyle}>
      <KpiCard
        testId="kpi-active-runs"
        label="Active Runs"
        value={data.activeRuns}
        icon={
          <RunIcon
            size={14}
            strokeWidth={ICON_STROKE_WIDTH}
            aria-hidden="true"
          />
        }
      />
      <KpiCard
        testId="kpi-pending-escalations"
        label="Pending Escalations"
        value={data.pendingEscalations}
        icon={
          <EscalationIcon
            size={14}
            strokeWidth={ICON_STROKE_WIDTH}
            aria-hidden="true"
          />
        }
      />
      <KpiCard
        testId="kpi-mini-app-events"
        label="Today's Mini-App Events"
        value={data.todayMiniAppEvents}
        icon={
          <MiniAppIcon
            size={14}
            strokeWidth={ICON_STROKE_WIDTH}
            aria-hidden="true"
          />
        }
      />
    </section>
  );
}
