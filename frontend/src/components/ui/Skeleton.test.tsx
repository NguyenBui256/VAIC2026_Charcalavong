/* Test: Skeleton — matches final layout, not generic spinner.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Skeleton from "./Skeleton";

describe("Skeleton", () => {
  it("renders a single-line skeleton", () => {
    render(<Skeleton width="200px" height="14px" />);
    const skel = screen.getByTestId("vaic-skeleton");
    expect(skel).toBeInTheDocument();
    expect(skel.className).toContain("vaic-skeleton");
  });

  it("renders multiple lines for text skeletons", () => {
    render(<Skeleton lines={3} />);
    const container = screen.getByTestId("vaic-skeleton");
    const lines = container.querySelectorAll(".vaic-skeleton");
    expect(lines.length).toBe(3);
  });

  it("last line of multiline skeleton is narrower (60%)", () => {
    render(<Skeleton lines={3} />);
    const container = screen.getByTestId("vaic-skeleton");
    const lines = container.querySelectorAll(".vaic-skeleton");
    const lastLine = lines[lines.length - 1] as HTMLElement;
    expect(lastLine.style.width).toBe("60%");
  });

  it("applies custom width and height", () => {
    render(<Skeleton width="100px" height="20px" />);
    const skel = screen.getByTestId("vaic-skeleton") as HTMLElement;
    expect(skel.style.width).toBe("100px");
    expect(skel.style.height).toBe("20px");
  });
});
