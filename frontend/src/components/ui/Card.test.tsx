/* Test: Card — 1px border, no default shadow, sm shadow when interactive (UX-DR5).
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Card from "./Card";

describe("Card", () => {
  it("renders with title and children", () => {
    render(
      <Card title="My Card">
        <p>Content</p>
      </Card>,
    );
    expect(screen.getByText("My Card")).toBeInTheDocument();
    expect(screen.getByText("Content")).toBeInTheDocument();
  });

  it("renders subtitle and headerAction", () => {
    render(
      <Card
        title="Title"
        subtitle="Subtitle text"
        headerAction={<button>Action</button>}
      >
        <p>Body</p>
      </Card>,
    );
    expect(screen.getByText("Subtitle text")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Action" })).toBeInTheDocument();
  });

  it("has vaic-card class and 1px border via CSS", () => {
    render(<Card title="T">Body</Card>);
    const card = screen.getByTestId("vaic-card");
    expect(card.className).toContain("vaic-card");
    // Non-interactive should NOT have the interactive class
    expect(card.className).not.toContain("vaic-card-interactive");
  });

  it("adds vaic-card-interactive class when interactive=true", () => {
    render(<Card title="T" interactive>Body</Card>);
    const card = screen.getByTestId("vaic-card");
    expect(card.className).toContain("vaic-card-interactive");
  });

  it("is clickable with keyboard (Enter/Space) when onClick provided", () => {
    const onClick = vi.fn();
    render(<Card title="T" onClick={onClick}>Body</Card>);
    const card = screen.getByTestId("vaic-card");
    expect(card).toHaveAttribute("role", "button");
    expect(card).toHaveAttribute("tabindex", "0");

    // Enter activates
    fireEvent.keyDown(card, { key: "Enter" });
    expect(onClick).toHaveBeenCalledTimes(1);

    // Space activates
    fireEvent.keyDown(card, { key: " " });
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it("calls onClick on mouse click", () => {
    const onClick = vi.fn();
    render(<Card title="T" onClick={onClick}>Body</Card>);
    fireEvent.click(screen.getByTestId("vaic-card"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
