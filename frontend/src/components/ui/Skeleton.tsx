/* Story 1.9 — Skeleton primitive (platform-design.md §5 Loading states).
 *
 * Skeletons match final layout, not generic spinners.
 * Pulse animation uses opacity only (UX-DR9 — transform/opacity only),
 * and freezes under prefers-reduced-motion via components.css.
 */

import type { CSSProperties } from "react";

export interface SkeletonProps {
  /** Width (CSS value). Defaults to 100%. */
  width?: string | number;
  /** Height (CSS value). Defaults to 14px (one line of text). */
  height?: string | number;
  /** Border radius. Defaults to var(--radius-control). */
  radius?: string;
  /** Inline style override. */
  style?: CSSProperties;
  /** Number of lines to render (for text skeletons). */
  lines?: number;
  /** Extra className. */
  className?: string;
}

export default function Skeleton({
  width = "100%",
  height = "14px",
  radius,
  style,
  lines = 1,
  className = "",
}: SkeletonProps) {
  if (lines > 1) {
    return (
      <div
        style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}
        className={className}
        data-testid="vaic-skeleton"
      >
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className="vaic-skeleton"
            style={{
              width: i === lines - 1 ? "60%" : "100%",
              height,
              borderRadius: radius,
            }}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className={`vaic-skeleton ${className}`.trim()}
      style={{ width, height, borderRadius: radius, ...style }}
      data-testid="vaic-skeleton"
    />
  );
}
