/* Story 1.9 — Shared Tooltip component.
 *
 * Simple CSS-based tooltip (no external dep) used by Button[variant=Icon]
 * and any component needing inline hover hints.
 *
 * Shows on hover and focus; hides on blur and mouse leave.
 * Respects prefers-reduced-motion via motion.css (opacity transition freezes).
 *
 * The tooltip bubble is portaled to <body> with position:fixed so it never
 * contributes to an ancestor's scroll area (an absolutely-positioned bubble
 * inside an `overflow:auto` table wrapper inflated scrollWidth -> phantom
 * horizontal scrollbar) and is never clipped by a scrolled container.
 */

import { useState, useRef, useLayoutEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";

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
  const wrapperRef = useRef<HTMLSpanElement>(null);
  const [coords, setCoords] = useState<{ left: number; top: number }>({ left: 0, top: 0 });

  // Position the portaled bubble against the trigger only while visible.
  useLayoutEffect(() => {
    if (!visible || !wrapperRef.current) return;
    const r = wrapperRef.current.getBoundingClientRect();
    const gap = 4;
    setCoords({
      left: r.left + r.width / 2,
      top: side === "bottom" ? r.bottom + gap : r.top - gap,
    });
  }, [visible, side]);

  const sideClass = side === "bottom" ? "vaic-tooltip-bottom" : "";

  return (
    <span
      ref={wrapperRef}
      className="vaic-tooltip-wrapper"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {createPortal(
        <span
          className={`vaic-tooltip ${sideClass} ${visible ? "vaic-tooltip-visible" : ""}`}
          role="tooltip"
          style={{ left: `${coords.left}px`, top: `${coords.top}px` }}
        >
          {label}
        </span>,
        document.body,
      )}
    </span>
  );
}
