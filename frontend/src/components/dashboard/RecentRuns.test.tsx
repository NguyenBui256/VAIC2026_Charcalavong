/* Test: RecentRuns — last 5 Runs per UX-DR15.
 * Loading / empty / error / populated states.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RecentRuns from "./RecentRuns";
import {
  mockDashboardPopulated,
  mockDashboardEmpty,
} from "../../lib/mockData";

describe("RecentRuns", () => {
  it("renders section heading", () => {
    render(<RecentRuns runs={mockDashboardPopulated.recentRuns} />);
    expect(
      screen.getByRole("heading", { name: /Recent Runs/i }),
    ).toBeInTheDocument();
  });

  it("renders at most 5 run rows", () => {
    render(<RecentRuns runs={mockDashboardPopulated.recentRuns} />);
    const rows = screen.getAllByTestId("recent-run-row");
    expect(rows).toHaveLength(5);
  });

  it("renders each run with name + status pill", () => {
    render(<RecentRuns runs={mockDashboardPopulated.recentRuns} />);
    expect(screen.getByText("Business Loan Pre-Screen")).toBeInTheDocument();
    expect(screen.getByText("AML Sweep Q3")).toBeInTheDocument();
    // Running pill present
    expect(screen.getByTestId("vaic-pill-running")).toBeInTheDocument();
    // Success pill present (multiple — at least one)
    expect(screen.getAllByTestId("vaic-pill-success").length).toBeGreaterThan(0);
  });

  it("renders duration for completed runs", () => {
    render(<RecentRuns runs={mockDashboardPopulated.recentRuns} />);
    // The success run "Business Loan #LOAN-203" has 22s duration
    expect(screen.getByText(/22s/)).toBeInTheDocument();
  });

  it("row click-to-trace fires onOpenRun with the run id", async () => {
    const onOpenRun = vi.fn();
    const user = userEvent.setup();
    render(
      <RecentRuns
        runs={mockDashboardPopulated.recentRuns}
        onOpenRun={onOpenRun}
      />,
    );
    const rows = screen.getAllByTestId("recent-run-row");
    await user.click(rows[1]); // Business Loan #LOAN-203
    expect(onOpenRun).toHaveBeenCalledWith("run-002");
  });

  it("renders EmptyState when there are no runs", () => {
    render(<RecentRuns runs={mockDashboardEmpty.recentRuns} />);
    expect(screen.getByTestId("vaic-empty-state")).toBeInTheDocument();
  });

  it("renders skeleton placeholders when loading", () => {
    render(<RecentRuns runs={[]} loading />);
    expect(screen.getAllByTestId("vaic-skeleton").length).toBeGreaterThan(0);
  });

  it("renders ErrorState when error is provided", () => {
    const retry = vi.fn();
    render(
      <RecentRuns runs={[]} error="network error" onRetry={retry} />,
    );
    expect(screen.getByTestId("vaic-error-state")).toBeInTheDocument();
  });
});
