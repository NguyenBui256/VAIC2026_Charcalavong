/* Test: lib/motion — motion tokens (UX-DR9).
 *
 * Verifies durations and easing match the design system spec exactly.
 */

import { describe, it, expect } from "vitest";
import { durations, easings, STEP_SLIDE_DISTANCE, transition } from "./motion";

describe("durations (UX-DR9)", () => {
  it("hover = 120ms", () => {
    expect(durations.hover).toBe(120);
  });
  it("modal = 200ms", () => {
    expect(durations.modal).toBe(200);
  });
  it("status (Run transition) = 240ms", () => {
    expect(durations.status).toBe(240);
  });
  it("step (trace) = 180ms", () => {
    expect(durations.step).toBe(180);
  });
  it("toast (escalation) = 280ms", () => {
    expect(durations.toast).toBe(280);
  });
  it("route (page) = 160ms", () => {
    expect(durations.route).toBe(160);
  });
});

describe("easings (UX-DR9)", () => {
  it("modal = cubic-bezier(0.16, 1, 0.3, 1)", () => {
    expect(easings.modal).toBe("cubic-bezier(0.16, 1, 0.3, 1)");
  });
});

describe("STEP_SLIDE_DISTANCE", () => {
  it("is 4px", () => {
    expect(STEP_SLIDE_DISTANCE).toBe(4);
  });
});

describe("transition() helper", () => {
  it("builds a transition string for transform + opacity", () => {
    const result = transition(["transform", "opacity"], 120);
    expect(result).toContain("transform 120ms");
    expect(result).toContain("opacity 120ms");
  });

  it("does not include width/height/top/left (UX-DR9)", () => {
    const result = transition(["transform", "opacity"], 200);
    expect(result).not.toMatch(/width|height|top|left/);
  });
});
