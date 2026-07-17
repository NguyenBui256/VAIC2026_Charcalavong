/* Test: EmptyState — illustration + CTA (UX-DR23).
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Search } from "lucide-react";
import EmptyState from "./EmptyState";

describe("EmptyState", () => {
  it("renders title and description", () => {
    render(<EmptyState title="No agents yet" description="Create your first" />);
    expect(screen.getByText("No agents yet")).toBeInTheDocument();
    expect(screen.getByText("Create your first")).toBeInTheDocument();
  });

  it("renders default Inbox icon", () => {
    render(<EmptyState title="Empty" />);
    const state = screen.getByTestId("vaic-empty-state");
    expect(state.querySelector("svg")).toBeTruthy();
  });

  it("renders custom icon", () => {
    render(<EmptyState title="No results" icon={<Search size={48} data-testid="custom-icon" />} />);
    expect(screen.getByTestId("custom-icon")).toBeInTheDocument();
  });

  it("renders action CTA", () => {
    render(
      <EmptyState title="No agents" action={<button>Create Agent</button>} />,
    );
    expect(screen.getByRole("button", { name: "Create Agent" })).toBeInTheDocument();
  });
});
