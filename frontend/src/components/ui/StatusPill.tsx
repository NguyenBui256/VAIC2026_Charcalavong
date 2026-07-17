/* Story 1.9 — StatusPill primitive (UX-DR4, UX-DR11).
 *
 * Renders icon + label for 6 Run/Task states. The icon + color mapping
 * is imported from lib/icons.tsx (the single source of truth), ensuring
 * the same visual language everywhere a state appears.
 *
 * Always icon + label (never color alone) per UX-DR11.
 */

import type { RunState } from "../../lib/icons";
import { stateMapping, ICON_STROKE_WIDTH } from "../../lib/icons";

export interface StatusPillProps {
  /** The Run / Task state. */
  state: RunState;
  /** Override the label text. Defaults to the canonical label from stateMapping. */
  label?: string;
  /** Additional className for custom sizing/positioning. */
  className?: string;
}

export default function StatusPill({
  state,
  label,
  className = "",
}: StatusPillProps) {
  const mapping = stateMapping[state];
  const Icon = mapping.icon;
  const displayLabel = label ?? mapping.label;

  return (
    <span
      className={`vaic-pill ${className}`.trim()}
      style={{
        background: mapping.softVar,
        color: mapping.colorVar,
      }}
      role="status"
      aria-live="polite"
      data-testid={`vaic-pill-${state}`}
    >
      <Icon
        size={12}
        strokeWidth={ICON_STROKE_WIDTH}
        className={mapping.spin ? "vaic-anim-spin" : undefined}
        aria-hidden="true"
      />
      <span>{displayLabel}</span>
    </span>
  );
}
