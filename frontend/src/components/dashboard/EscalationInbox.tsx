/* Story 1.10 — Escalation inbox preview (UX-DR15).
 *
 * Shows the top 3 pending escalations with Run name, escalation reason,
 * and an "Open" affordance. Empty / loading / error per UX-DR23.
 */

import type { CSSProperties } from "react";
import { AlertTriangle } from "lucide-react";
import { Card, EmptyState, Skeleton, ErrorState, Button } from "../ui";
import { ICON_STROKE_WIDTH, semanticIcons } from "../../lib/icons";
import {
  formatRelativeFromOffset,
  type EscalationItem,
} from "../../lib/mockData";

export interface EscalationInboxProps {
  items: EscalationItem[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  /** Called with the runId when the user clicks "Open". */
  onOpen?: (runId: string) => void;
}

const EscalationIcon = semanticIcons.Escalation;

function EscalationRow({
  item,
  onOpen,
}: {
  item: EscalationItem;
  onOpen?: (runId: string) => void;
}) {
  const rowStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: "var(--space-1)",
    padding: "var(--space-3) 0",
    borderBottom: "1px solid var(--color-border)",
  };

  return (
    <div style={rowStyle}>
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: "var(--space-2)",
        }}
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "var(--space-1)",
            color: "var(--color-escalated)",
            flex: 1,
            minWidth: 0,
          }}
        >
          <AlertTriangle
            size={14}
            strokeWidth={ICON_STROKE_WIDTH}
            aria-hidden="true"
            style={{ flexShrink: 0 }}
          />
          <span
            className="text-body"
            style={{ fontWeight: 500, color: "var(--color-text)" }}
          >
            {item.runName}
          </span>
        </span>
        {onOpen && (
          <Button
            variant="secondary"
            onClick={() => onOpen(item.runId)}
            aria-label={`Open escalation for ${item.runName}`}
            style={{ flexShrink: 0 }}
          >
            Open
          </Button>
        )}
      </div>
      <span
        className="text-small"
        style={{ color: "var(--color-text-tertiary)" }}
      >
        {item.reason}
      </span>
      <span
        className="text-small"
        style={{ color: "var(--color-text-tertiary)" }}
      >
        {formatRelativeFromOffset(item.createdAtOffsetMs)}
      </span>
    </div>
  );
}

function EscalationSkeleton() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-2)",
        padding: "var(--space-3) 0",
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      <Skeleton width="60%" height="16px" />
      <Skeleton width="80%" height="12px" />
      <Skeleton width="40%" height="12px" />
    </div>
  );
}

export default function EscalationInbox({
  items,
  loading = false,
  error = null,
  onRetry,
  onOpen,
}: EscalationInboxProps) {
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
          <EscalationSkeleton />
          <EscalationSkeleton />
          <EscalationSkeleton />
        </>
      );
    }
    if (items.length === 0) {
      return (
        <EmptyState
          icon={<EscalationIcon size={48} strokeWidth={ICON_STROKE_WIDTH} />}
          title="No pending escalations"
          description="Items needing your review will appear here."
        />
      );
    }
    return items.slice(0, 3).map((item, idx, arr) => (
      <div
        key={item.id}
        style={
          idx === arr.length - 1
            ? { borderBottom: "none" }
            : undefined
        }
      >
        <EscalationRow item={item} onOpen={onOpen} />
      </div>
    ));
  };

  return (
    <Card
      as="section"
      title="Needs your attention"
      subtitle={
        loading || error
          ? undefined
          : `${items.length} pending`
      }
      headerAction={
        <EscalationIcon
          size={18}
          strokeWidth={ICON_STROKE_WIDTH}
          style={{ color: "var(--color-escalated)" }}
          aria-hidden="true"
        />
      }
    >
      {renderBody()}
    </Card>
  );
}
