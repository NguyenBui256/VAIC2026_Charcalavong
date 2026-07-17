/* Test: ThemeToggle flips data-theme attribute on <html>.
 */

import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ThemeToggle from "./ThemeToggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    document.documentElement.removeAttribute("data-theme");
    localStorage.clear();
  });

  it("renders a button with aria-label", () => {
    render(<ThemeToggle />);
    const btn = screen.getByRole("button");
    expect(btn).toHaveAttribute("aria-label");
  });

  it("toggles data-theme on <html> when clicked", () => {
    // Start with light (no prefers-color-scheme in jsdom → defaults to light)
    render(<ThemeToggle />);
    const btn = screen.getByRole("button");

    // Initial theme should be light
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");

    // Click → should switch to dark
    fireEvent.click(btn);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    // Click again → back to light
    fireEvent.click(btn);
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });
});
