/* Test: EscalationInbox — top 3 pending items per UX-DR15.
 * Loading / empty / error / populated states.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EscalationInbox from "./EscalationInbox";
import {
  mockDashboardPopulated,
  mockDashboardEmpty,
  type EscalationItem,
} from "../../lib/mockData";

describe("EscalationInbox", () => {
  it("renders section heading", () => {
    render(<EscalationInbox items={mockDashboardPopulated.escalations} />);
    expect(
      screen.getByRole("heading", { name: /Needs your attention/i }),
    ).toBeInTheDocument();
  });

  it("renders each escalation row with Run name and reason", () => {
    render(<EscalationInbox items={mockDashboardPopulated.escalations} />);
    expect(screen.getByText("Business Loan #LOAN-204")).toBeInTheDocument();
    expect(
      screen.getByText("Compliance vs Credit conflict"),
    ).toBeInTheDocument();
  });

  it("renders an 'Open' affordance per escalation that fires onOpen", async () => {
    const onOpen = vi.fn();
    const items: EscalationItem[] = [
      {
        id: "esc-test",
        runId: "run-1",
        runName: "Test Run",
        reason: "Test reason",
        createdAtOffsetMs: -1000,
      },
    ];
    render(<EscalationInbox items={items} onOpen={onOpen} />);
    const openBtn = screen.getByRole("button", { name: /Open/i });
    await userEvent.click(openBtn);
    expect(onOpen).toHaveBeenCalledWith("run-1");
  });

  it("renders EmptyState when there are zero escalations", () => {
    render(<EscalationInbox items={mockDashboardEmpty.escalations} />);
    expect(screen.getByTestId("vaic-empty-state")).toBeInTheDocument();
  });

  it("renders skeleton placeholders when loading", () => {
    render(<EscalationInbox items={[]} loading />);
    expect(screen.getAllByTestId("vaic-skeleton").length).toBeGreaterThan(0);
    expect(
      screen.queryByRole("heading", { name: /Needs your attention/i }),
    ).toBeInTheDocument();
  });

  it("renders ErrorState when error is provided", () => {
    const retry = vi.fn();
    render(<EscalationInbox items={[]} error="fetch failed" onRetry={retry} />);
    expect(screen.getByTestId("vaic-error-state")).toBeInTheDocument();
  });
});
