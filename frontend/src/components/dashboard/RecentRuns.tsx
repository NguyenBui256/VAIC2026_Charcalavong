/* Story 1.10 — Recent Runs list (UX-DR15).
 *
 * Shows the last 5 Runs with name, status pill, run-time (duration), and a
 * click-to-trace affordance (row is keyboard-activatable). Empty / loading /
 * error per UX-DR23.
 */

import type { CSSProperties } from "react";
import { Card, StatusPill, EmptyState, Skeleton, ErrorState } from "../ui";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../lib/icons";
import {
  formatDuration,
  formatRelativeFromOffset,
  type RunSummary,
} from "../../lib/mockData";

export interface RecentRunsProps {
  runs: RunSummary[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  /** Called with the runId when the user activates a row (click-to-trace). */
  onOpenRun?: (runId: string) => void;
}

const RunIcon = semanticIcons.Run;

function RunRow({
  run,
  onOpenRun,
}: {
  run: RunSummary;
  onOpenRun?: (runId: string) => void;
}) {
  const rowStyle: CSSProperties = {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "var(--space-2)",
    padding: "var(--space-3) 0",
    borderBottom: "1px solid var(--color-border)",
    cursor: onOpenRun ? "pointer" : "default",
    textAlign: "left",
    width: "100%",
    background: "transparent",
    border: "none",
    borderBottomWidth: 1,
    borderBottomStyle: "solid",
    borderBottomColor: "var(--color-border)",
    color: "inherit",
    font: "inherit",
  };

  const handleClick = () => onOpenRun?.(run.id);
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!onOpenRun) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onOpenRun(run.id);
    }
  };

  return (
    <div
      data-testid="recent-run-row"
      role={onOpenRun ? "button" : undefined}
      tabIndex={onOpenRun ? 0 : undefined}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      style={rowStyle}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-1)",
          minWidth: 0,
          flex: 1,
        }}
      >
        <span
          className="text-body"
          style={{ fontWeight: 500, color: "var(--color-text)" }}
        >
          {run.name}
        </span>
        <span
          className="text-small"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          {formatRelativeFromOffset(run.startedAtOffsetMs)}
        </span>
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-3)",
          flexShrink: 0,
        }}
      >
        {run.state !== "pending" && run.state !== "running" && (
          <span
            className="text-small"
            style={{
              color: "var(--color-text-tertiary)",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {formatDuration(run.durationMs)}
          </span>
        )}
        <StatusPill state={run.state} />
      </div>
    </div>
  );
}

function RunSkeleton() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "var(--space-2)",
        padding: "var(--space-3) 0",
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-1)",
          flex: 1,
        }}
      >
        <Skeleton width="50%" height="16px" />
        <Skeleton width="25%" height="12px" />
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2)",
        }}
      >
        <Skeleton width="30px" height="12px" />
        <Skeleton width="64px" height="20px" radius="999px" />
      </div>
    </div>
  );
}

export default function RecentRuns({
  runs,
  loading = false,
  error = null,
  onRetry,
  onOpenRun,
}: RecentRunsProps) {
  const renderBody = () => {
    if (error) {
      return (
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
      );
    }
    if (loading) {
      return (
        <>
          <RunSkeleton />
          <RunSkeleton />
          <RunSkeleton />
          <RunSkeleton />
          <RunSkeleton />
        </>
      );
    }
    if (runs.length === 0) {
      return (
        <EmptyState
          icon={<RunIcon size={48} strokeWidth={ICON_STROKE_WIDTH} />}
          title="No runs yet"
          description="Run a workflow to see its trace appear here."
        />
      );
    }
    return runs.slice(0, 5).map((run) => (
      <RunRow key={run.id} run={run} onOpenRun={onOpenRun} />
    ));
  };

  return (
    <Card
      as="section"
      title="Recent Runs"
      subtitle={
        loading || error ? undefined : `Last ${Math.min(runs.length, 5)} runs`
      }
      headerAction={
        <RunIcon
          size={18}
          strokeWidth={ICON_STROKE_WIDTH}
          style={{ color: "var(--color-text-tertiary)" }}
          aria-hidden="true"
        />
      }
    >
      {renderBody()}
    </Card>
  );
}
