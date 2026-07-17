/* Story 1.9 — ErrorState primitive (platform-design.md §5 Error states).
 *
 * Shows error message + optional retry action. Used for page-level errors,
 * failed data fetches, and run-level failures.
 */

import type { ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { ICON_STROKE_WIDTH } from "../../lib/icons";

export interface ErrorStateProps {
  /** Error message to display. */
  message: string;
  /** Optional secondary detail / cause. */
  detail?: string;
  /** Optional retry button / action node. */
  retry?: ReactNode;
}

export default function ErrorState({
  message,
  detail,
  retry,
}: ErrorStateProps) {
  return (
    <div
      className="vaic-error-state"
      data-testid="vaic-error-state"
      role="alert"
      aria-live="assertive"
    >
      <AlertTriangle
        size={48}
        strokeWidth={ICON_STROKE_WIDTH}
        style={{ color: "var(--color-destructive)" }}
      />
      <h3
        className="text-h3"
        style={{ color: "var(--color-destructive)", margin: 0 }}
      >
        {message}
      </h3>
      {detail && (
        <p
          className="text-small"
          style={{ color: "var(--color-text-tertiary)", maxWidth: "400px" }}
        >
          {detail}
        </p>
      )}
      {retry && <div style={{ marginTop: "var(--space-2)" }}>{retry}</div>}
    </div>
  );
}
