/* Test: Tooltip — shared tooltip component.
 */

import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Tooltip from "./Tooltip";

describe("Tooltip", () => {
  it("renders children", () => {
    render(
      <Tooltip label="Hint">
        <button>Hover me</button>
      </Tooltip>,
    );
    expect(screen.getByRole("button", { name: "Hover me" })).toBeInTheDocument();
  });

  it("renders tooltip with role=tooltip", () => {
    render(
      <Tooltip label="Help text">
        <button>Btn</button>
      </Tooltip>,
    );
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    expect(screen.getByRole("tooltip").textContent).toBe("Help text");
  });

  it("shows tooltip on mouse enter", () => {
    render(
      <Tooltip label="Visible">
        <button>Btn</button>
      </Tooltip>,
    );
    const wrapper = screen.getByRole("button", { name: "Btn" }).parentElement!;
    const tip = screen.getByRole("tooltip");
    expect(tip.className).not.toContain("vaic-tooltip-visible");

    fireEvent.mouseEnter(wrapper);
    expect(tip.className).toContain("vaic-tooltip-visible");

    fireEvent.mouseLeave(wrapper);
    expect(tip.className).not.toContain("vaic-tooltip-visible");
  });

  it("shows tooltip on focus (keyboard nav)", () => {
    render(
      <Tooltip label="Focused">
        <button>Btn</button>
      </Tooltip>,
    );
    const wrapper = screen.getByRole("button", { name: "Btn" }).parentElement!;
    const tip = screen.getByRole("tooltip");
    fireEvent.focus(wrapper);
    expect(tip.className).toContain("vaic-tooltip-visible");
  });
});
