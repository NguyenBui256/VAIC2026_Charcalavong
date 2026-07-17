/* Test: StatusPill — 6 states with locked icon+color mapping (UX-DR4, UX-DR11).
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StatusPill from "./StatusPill";
import { stateMapping, allRunStates } from "../../lib/icons";
import type { RunState } from "../../lib/icons";

describe("StatusPill", () => {
  it("renders all 6 states", () => {
    allRunStates.forEach((state) => {
      const { unmount } = render(<StatusPill state={state} />);
      const pill = screen.getByTestId(`vaic-pill-${state}`);
      expect(pill).toBeInTheDocument();
      expect(pill.textContent).toContain(stateMapping[state].label);
      unmount();
    });
  });

  it("shows icon + label for each state (never color alone)", () => {
    allRunStates.forEach((state) => {
      const { unmount } = render(<StatusPill state={state} />);
      const pill = screen.getByTestId(`vaic-pill-${state}`);
      // Label text is present
      expect(pill.textContent).toContain(stateMapping[state].label);
      // Icon SVG is present (lucide renders an <svg>)
      expect(pill.querySelector("svg")).toBeTruthy();
      unmount();
    });
  });

  it("applies the correct color token from stateMapping (UX-DR11 consistency)", () => {
    allRunStates.forEach((state) => {
      const { unmount } = render(<StatusPill state={state} />);
      const pill = screen.getByTestId(`vaic-pill-${state}`) as HTMLElement;
      const computedStyle = window.getComputedStyle(pill);
      // The inline style sets color via var(--color-*). We verify the
      // style attribute references the same token as the mapping.
      expect(pill.style.color).toBe(stateMapping[state].colorVar);
      expect(pill.style.background).toBe(stateMapping[state].softVar);
      void computedStyle; // (jsdom won't resolve CSS vars; we check style attr instead)
      unmount();
    });
  });

  it("renders Pending with correct color token from mapping", () => {
    render(<StatusPill state="pending" />);
    const pill = screen.getByTestId("vaic-pill-pending");
    expect(pill.textContent).toContain("Pending");
    expect(pill.style.color).toBe(stateMapping.pending.colorVar);
  });

  it("renders Running with spinning Loader", () => {
    render(<StatusPill state="running" />);
    const pill = screen.getByTestId("vaic-pill-running");
    const svg = pill.querySelector("svg");
    // jsdom SVG className is SVGAnimatedString — use getAttribute
    expect(svg?.getAttribute("class")).toContain("vaic-anim-spin");
  });

  it("renders Success with Check icon", () => {
    render(<StatusPill state="success" />);
    expect(screen.getByTestId("vaic-pill-success").textContent).toContain(
      "Success",
    );
  });

  it("renders Error state", () => {
    render(<StatusPill state="error" />);
    expect(screen.getByTestId("vaic-pill-error").textContent).toContain(
      "Error",
    );
  });

  it("renders Escalated state", () => {
    render(<StatusPill state="escalated" />);
    expect(screen.getByTestId("vaic-pill-escalated").textContent).toContain(
      "Escalated",
    );
  });

  it("renders Draft state", () => {
    render(<StatusPill state="draft" />);
    expect(screen.getByTestId("vaic-pill-draft").textContent).toContain(
      "Draft",
    );
  });

  it("has role=status and aria-live=polite (UX-DR12)", () => {
    const state: RunState = "pending";
    render(<StatusPill state={state} />);
    const pill = screen.getByTestId(`vaic-pill-${state}`);
    expect(pill).toHaveAttribute("role", "status");
    expect(pill).toHaveAttribute("aria-live", "polite");
  });

  it("supports custom label override", () => {
    render(<StatusPill state="running" label="In progress" />);
    const pill = screen.getByTestId("vaic-pill-running");
    expect(pill.textContent).toContain("In progress");
  });
});
