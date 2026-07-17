/* Story 1.9 — Shared Tooltip component.
 *
 * Simple CSS-based tooltip (no external dep) used by Button[variant=Icon]
 * and any component needing inline hover hints.
 *
 * Shows on hover and focus; hides on blur and mouse leave.
 * Respects prefers-reduced-motion via motion.css (opacity transition freezes).
 */

import { useState, type ReactNode } from "react";

export interface TooltipProps {
  /** Tooltip text. */
  label: string;
  /** The element that triggers the tooltip on hover/focus. */
  children: ReactNode;
  /** Optional side placement. Defaults to "top". */
  side?: "top" | "bottom";
}

export default function Tooltip({
  label,
  children,
  side = "top",
}: TooltipProps) {
  const [visible, setVisible] = useState(false);

  const sideClass =
    side === "bottom"
      ? "vaic-tooltip-bottom"
      : "";

  return (
    <span
      className="vaic-tooltip-wrapper"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      <span
        className={`vaic-tooltip ${sideClass} ${visible ? "vaic-tooltip-visible" : ""}`}
        role="tooltip"
      >
        {label}
      </span>
    </span>
  );
}
