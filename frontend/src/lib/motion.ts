/* Story 1.9 — Motion tokens (UX-DR9).
 *
 * Single source of truth for all animation durations and easing curves.
 * Components MUST reference these tokens, never hardcode duration values.
 *
 * Rules enforced by design review:
 *  - Only `transform` and `opacity` may be animated (never width/height/top/left).
 *  - `prefers-reduced-motion` freezes all animations (see styles/motion.css).
 *  - Trace timeline updates are interruptible — new step cancels in-flight animation.
 */

/** Motion durations (ms) — mirror `--duration-*` CSS custom properties in tokens.css. */
export const durations = {
  /** Hover / press feedback. */
  hover: 120,
  /** Modal / drawer open. */
  modal: 200,
  /** Run status transition (pill color / icon swap). */
  status: 240,
  /** Trace step appears (fade + 4px slide-up). */
  step: 180,
  /** Escalation toast slide-in from top-right. */
  toast: 280,
  /** Page / route transition cross-fade. */
  route: 160,
} as const;

/** Easing curves — mirror `--ease-*` CSS custom properties in tokens.css. */
export const easings = {
  /**
   * Modal / drawer open — the canonical VAIC easing.
   * `cubic-bezier(0.16, 1, 0.3, 1)` (per UX-DR9).
   */
  modal: "cubic-bezier(0.16, 1, 0.3, 1)",
  /** General ease-out for hover / status / step / toast. */
  out: "cubic-bezier(0.16, 1, 0.3, 1)",
  /** Symmetric ease-in-out for route cross-fades. */
  inOut: "cubic-bezier(0.4, 0, 0.2, 1)",
} as const;

/** Trace step slide-up distance (px). Only `transform` is animated. */
export const STEP_SLIDE_DISTANCE = 4;

/**
 * Build a transition string that respects the "transform/opacity only" rule.
 * Use this helper to keep all component transitions consistent.
 */
export function transition(
  properties: Array<"transform" | "opacity" | "background" | "color" | "border-color" | "box-shadow">,
  duration: number = durations.hover,
  easing: string = easings.out,
): string {
  return properties
    .map((p) => `${p} ${duration}ms ${easing}`)
    .join(", ");
}

/** Type narrowing helper so consumers can't typo variant names. */
export type MotionDuration = keyof typeof durations;
export type MotionEasing = keyof typeof easings;
