/* Story 1.9 — Button primitive (UX-DR3).
 *
 * 5 variants: Primary, Secondary, Ghost, Destructive, Icon.
 * Min height 36px, 8px padding-y, 16px padding-x (enforced in components.css).
 * Icon variant requires aria-label + tooltip.
 *
 * AC: Only one Primary CTA per view — enforced via runtime console.warn in dev
 * when more than one Primary button is mounted in the same React tree.
 */

import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";
import Tooltip from "./Tooltip";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "ghost"
  | "destructive"
  | "icon";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  /** Optional leading icon (Lucide component element). */
  icon?: ReactNode;
  /** Tooltip text (required for `icon` variant, optional otherwise). */
  tooltip?: string;
  children?: ReactNode;
}

/* ────────────────────────────────────────────────────────────────────
 * Single Primary CTA enforcement (UX-DR3).
 *
 * Module-level counter. Each mounted <Button variant="primary"> increments
 * on mount and decrements on unmount. When count > 1, console.warn in dev.
 * ──────────────────────────────────────────────────────────────────── */

let primaryCount = 0;

/** Read the current Primary button count (for tests). */
export function getPrimaryCount(): number {
  return primaryCount;
}

/** Reset counter — for test isolation. */
export function _resetPrimaryCount(): void {
  primaryCount = 0;
}

function incrementPrimary(): void {
  primaryCount++;
  if (primaryCount > 1 && import.meta.env.DEV) {
    console.warn(
      `[VAIC] More than one Primary CTA mounted (${primaryCount}). ` +
        "UX-DR3 requires a single Primary button per view.",
    );
  }
}

function decrementPrimary(): void {
  primaryCount = Math.max(0, primaryCount - 1);
}

export default function Button({
  variant = "secondary",
  icon,
  tooltip,
  children,
  className = "",
  ...rest
}: ButtonProps) {
  const isIcon = variant === "icon";

  useEffect(() => {
    if (variant === "primary") {
      incrementPrimary();
      return () => decrementPrimary();
    }
  }, [variant]);

  // Icon variant requires aria-label (UX-DR3) — dev-only warning.
  if (isIcon && !rest["aria-label"] && import.meta.env.DEV) {
    console.warn(
      "[VAIC] Button variant='icon' requires an aria-label for accessibility (UX-DR3).",
    );
  }

  const variantClass = `vaic-btn-${variant}`;
  const classes = `vaic-btn ${variantClass} vaic-focusable ${className}`.trim();

  const button = (
    <button className={classes} {...rest}>
      {icon}
      {children}
    </button>
  );

  if (isIcon) {
    const tip = tooltip ?? (rest["aria-label"] as string | undefined) ?? "";
    return <Tooltip label={tip}>{button}</Tooltip>;
  }

  if (tooltip) {
    return <Tooltip label={tooltip}>{button}</Tooltip>;
  }

  return button;
}
