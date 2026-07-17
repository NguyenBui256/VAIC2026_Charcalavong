/* Story 1.9 — Card primitive (UX-DR5).
 *
 * 1px border with --color-border, no default shadow.
 * Shadow sm only when interactive=true (clickable) or floating.
 */

import type { ReactNode, MouseEvent } from "react";

export interface CardProps {
  /** Card title (rendered as h3). */
  title?: ReactNode;
  /** Optional subtitle / metadata row below the title. */
  subtitle?: ReactNode;
  /** Optional node rendered on the right side of the header (e.g. StatusPill). */
  headerAction?: ReactNode;
  /** Card body content. */
  children?: ReactNode;
  /** When true, card gets sm shadow and hover styling (UX-DR5). */
  interactive?: boolean;
  /** Click handler — presence implies interactive. */
  onClick?: (e: MouseEvent<HTMLDivElement>) => void;
  /** Extra className. */
  className?: string;
  /** HTML element for the container. Defaults to div. */
  as?: "div" | "section" | "article";
}

export default function Card({
  title,
  subtitle,
  headerAction,
  children,
  interactive = false,
  onClick,
  className = "",
  as: Tag = "div",
}: CardProps) {
  const isInteractive = interactive || Boolean(onClick);
  const classes = `vaic-card ${isInteractive ? "vaic-card-interactive" : ""} ${className}`.trim();

  const hasHeader = title || subtitle || headerAction;

  return (
    <Tag
      className={classes}
      onClick={onClick}
      role={isInteractive && onClick ? "button" : undefined}
      tabIndex={isInteractive && onClick ? 0 : undefined}
      onKeyDown={
        isInteractive && onClick
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick(e as unknown as MouseEvent<HTMLDivElement>);
              }
            }
          : undefined
      }
      data-testid="vaic-card"
    >
      {hasHeader && (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: "var(--space-2)",
            marginBottom: children ? "var(--space-3)" : 0,
          }}
        >
          <div style={{ minWidth: 0 }}>
            {title && (
              <h3
                className="text-h3"
                style={{ color: "var(--color-text)" }}
              >
                {title}
              </h3>
            )}
            {subtitle && (
              <div
                className="text-small"
                style={{ color: "var(--color-text-tertiary)", marginTop: title ? "var(--space-1)" : 0 }}
              >
                {subtitle}
              </div>
            )}
          </div>
          {headerAction && <div style={{ flexShrink: 0 }}>{headerAction}</div>}
        </div>
      )}
      {children}
    </Tag>
  );
}
