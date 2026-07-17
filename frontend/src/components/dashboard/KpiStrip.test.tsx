/* Test: KpiStrip — three KPI cards per UX-DR15.
 * Loading / empty / error / populated states.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import KpiStrip from "./KpiStrip";
import {
  mockDashboardPopulated,
  mockDashboardEmpty,
} from "../../lib/mockData";

describe("KpiStrip", () => {
  it("renders three KPI cards in populated state", () => {
    render(<KpiStrip data={mockDashboardPopulated.kpis} />);
    expect(screen.getByTestId("kpi-active-runs")).toHaveTextContent("2");
    expect(screen.getByTestId("kpi-pending-escalations")).toHaveTextContent(
      "1",
    );
    expect(screen.getByTestId("kpi-mini-app-events")).toHaveTextContent("14");
  });

  it("renders the three KPI labels (Active Runs, Pending Escalations, Today's Mini-App Events)", () => {
    render(<KpiStrip data={mockDashboardPopulated.kpis} />);
    expect(screen.getByText("Active Runs")).toBeInTheDocument();
    expect(screen.getByText("Pending Escalations")).toBeInTheDocument();
    expect(screen.getByText(/Mini-App Events/)).toBeInTheDocument();
  });

  it("renders zeros in empty state (not blank)", () => {
    render(<KpiStrip data={mockDashboardEmpty.kpis} />);
    expect(screen.getByTestId("kpi-active-runs")).toHaveTextContent("0");
    expect(screen.getByTestId("kpi-pending-escalations")).toHaveTextContent(
      "0",
    );
    expect(screen.getByTestId("kpi-mini-app-events")).toHaveTextContent("0");
  });

  it("renders three skeleton placeholders when loading", () => {
    render(<KpiStrip loading />);
    const skeletons = screen.getAllByTestId("vaic-skeleton");
    expect(skeletons.length).toBeGreaterThanOrEqual(3);
    // Loading state should NOT render numbers
    expect(screen.queryByText("Active Runs")).not.toBeInTheDocument();
  });

  it("renders an error state with retry", () => {
    const retry = vi.fn();
    render(<KpiStrip error="Failed to load" onRetry={retry} />);
    expect(screen.getByTestId("vaic-error-state")).toBeInTheDocument();
    expect(screen.getByText(/Failed to load/)).toBeInTheDocument();
  });
});
