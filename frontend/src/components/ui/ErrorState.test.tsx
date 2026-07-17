/* Test: ErrorState — error message + retry action (platform-design.md §5).
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ErrorState from "./ErrorState";

describe("ErrorState", () => {
  it("renders error message", () => {
    render(<ErrorState message="Failed to load" />);
    expect(screen.getByText("Failed to load")).toBeInTheDocument();
  });

  it("renders detail text", () => {
    render(
      <ErrorState message="Error" detail="Network timeout occurred" />,
    );
    expect(screen.getByText("Network timeout occurred")).toBeInTheDocument();
  });

  it("renders retry action", () => {
    const onRetry = vi.fn();
    render(
      <ErrorState
        message="Error"
        retry={<button onClick={onRetry}>Retry</button>}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("has role=alert and aria-live=assertive (UX-DR12)", () => {
    render(<ErrorState message="Something went wrong" />);
    const state = screen.getByTestId("vaic-error-state");
    expect(state).toHaveAttribute("role", "alert");
    expect(state).toHaveAttribute("aria-live", "assertive");
  });

  it("renders AlertTriangle icon in destructive color", () => {
    render(<ErrorState message="Error" />);
    const state = screen.getByTestId("vaic-error-state");
    const svg = state.querySelector("svg") as SVGElement;
    expect(svg).toBeTruthy();
    // The AlertTriangle icon gets inline style color=var(--color-destructive)
    expect(svg.style.color).toBe("var(--color-destructive)");
  });
});
