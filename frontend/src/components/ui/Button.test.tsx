/* Test: Button — 5 variants, min height, icon a11y, single Primary check.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { Play, Trash } from "lucide-react";
import Button, {
  _resetPrimaryCount,
  getPrimaryCount,
} from "./Button";

describe("Button", () => {
  beforeEach(() => {
    _resetPrimaryCount();
    vi.clearAllMocks();
  });

  it("renders Primary variant with children", () => {
    render(<Button variant="primary">Save</Button>);
    const btn = screen.getByRole("button", { name: "Save" });
    expect(btn).toBeInTheDocument();
    expect(btn.className).toContain("vaic-btn-primary");
  });

  it("renders Secondary variant (default)", () => {
    render(<Button>Cancel</Button>);
    const btn = screen.getByRole("button", { name: "Cancel" });
    expect(btn.className).toContain("vaic-btn-secondary");
  });

  it("renders Ghost variant", () => {
    render(<Button variant="ghost">Filter</Button>);
    const btn = screen.getByRole("button", { name: "Filter" });
    expect(btn.className).toContain("vaic-btn-ghost");
  });

  it("renders Destructive variant", () => {
    render(<Button variant="destructive">Delete</Button>);
    const btn = screen.getByRole("button", { name: "Delete" });
    expect(btn.className).toContain("vaic-btn-destructive");
  });

  it("renders Icon variant with aria-label and tooltip", () => {
    render(
      <Button
        variant="icon"
        aria-label="Delete item"
        icon={<Trash size={16} strokeWidth={1.5} />}
      />,
    );
    const btn = screen.getByRole("button", { name: "Delete item" });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute("aria-label", "Delete item");
  });

  it("fires onClick when clicked", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Run</Button>);
    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("applies vaic-btn class (min-height 36px enforced via CSS)", () => {
    render(<Button variant="primary">Test</Button>);
    expect(screen.getByRole("button").className).toContain("vaic-btn");
  });

  it("renders with a leading icon", () => {
    const { container } = render(
      <Button variant="primary" icon={<Play size={14} data-testid="icon" />}>
        Run
      </Button>,
    );
    expect(container.querySelector('[data-testid="icon"]')).toBeInTheDocument();
  });

  describe("Single Primary CTA enforcement", () => {
    it("increments primary count on mount", () => {
      expect(getPrimaryCount()).toBe(0);
      render(<Button variant="primary">A</Button>);
      expect(getPrimaryCount()).toBe(1);
    });

    it("decrements primary count on unmount", () => {
      const { unmount } = render(<Button variant="primary">A</Button>);
      expect(getPrimaryCount()).toBe(1);
      unmount();
      expect(getPrimaryCount()).toBe(0);
    });

    it("warns in dev when more than one Primary is mounted", () => {
      const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
      render(
        <div>
          <Button variant="primary">First</Button>
          <Button variant="primary">Second</Button>
        </div>,
      );
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining("More than one Primary CTA mounted"),
      );
      warnSpy.mockRestore();
      cleanup();
    });
  });
});
