/* Test: AgentStatusPill — Draft reuses StatusPill, Active is a dedicated pill. */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import AgentStatusPill from "./AgentStatusPill";

describe("AgentStatusPill", () => {
  it("renders the Draft StatusPill for status=draft", () => {
    render(<AgentStatusPill status="draft" />);
    expect(screen.getByTestId("vaic-pill-draft")).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
  });

  it("renders a dedicated Active pill for status=active", () => {
    render(<AgentStatusPill status="active" />);
    expect(screen.getByTestId("vaic-pill-active")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });
});
