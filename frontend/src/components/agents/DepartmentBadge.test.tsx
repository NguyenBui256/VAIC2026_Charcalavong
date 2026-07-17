/* Test: DepartmentBadge — renders the department name + icon. */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import DepartmentBadge from "./DepartmentBadge";

describe("DepartmentBadge", () => {
  it("renders the department name", () => {
    render(<DepartmentBadge name="Retail Lending" />);
    expect(screen.getByTestId("vaic-department-badge")).toBeInTheDocument();
    expect(screen.getByText("Retail Lending")).toBeInTheDocument();
  });
});
