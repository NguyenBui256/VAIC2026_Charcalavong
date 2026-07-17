/* Story 1.9 — EmptyState primitive (UX-DR23).
 *
 * Genuine empty state with illustration icon + one-line explanation + CTA.
 * Used by lists/tables when there's no data yet (platform-design.md §5).
 */

import type { ReactNode } from "react";
import { Inbox } from "lucide-react";
import { ICON_STROKE_WIDTH } from "../../lib/icons";

export interface EmptyStateProps {
  /** Lucide icon element (sized 48px). Defaults to Inbox. */
  icon?: ReactNode;
  /** Headline — typically the "what" of the empty state. */
  title: string;
  /** One-line explanation below the title. */
  description?: string;
  /** Optional CTA button / link. */
  action?: ReactNode;
}

export default function EmptyState({
  icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="vaic-empty-state" data-testid="vaic-empty-state">
      <div className="vaic-empty-state-icon">
        {icon ?? <Inbox size={48} strokeWidth={ICON_STROKE_WIDTH} />}
      </div>
      <h3
        className="text-h3"
        style={{ color: "var(--color-text)", margin: 0 }}
      >
        {title}
      </h3>
      {description && (
        <p
          className="text-small"
          style={{ color: "var(--color-text-tertiary)", maxWidth: "400px" }}
        >
          {description}
        </p>
      )}
      {action && <div style={{ marginTop: "var(--space-2)" }}>{action}</div>}
    </div>
  );
}
