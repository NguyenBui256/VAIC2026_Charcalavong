/* Test: DashboardPage — three sections per UX-DR15.
 * Wires TanStack Query + MemoryRouter. Tests the populated state end-to-end;
 * loading / empty / error are covered at the component level.
 */

import { describe, it, expect, beforeAll, beforeEach, afterAll } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardPage from "./dashboard";
import {
  __setDashboardMockMode,
  __setDashboardMockDelay,
  __resetDashboardMock,
} from "../hooks/useDashboardData";

function renderDashboard() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  beforeAll(() => {
    __setDashboardMockDelay(0);
  });

  beforeEach(() => {
    __resetDashboardMock();
    __setDashboardMockDelay(0);
  });

  afterAll(() => {
    __resetDashboardMock();
  });

  it("renders the page heading", async () => {
    renderDashboard();
    expect(
      screen.getByRole("heading", { name: /^Dashboard$/i }),
    ).toBeInTheDocument();
  });

  it("renders all three sections (KPI strip, Escalation inbox, Recent Runs)", async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByTestId("kpi-strip")).toBeInTheDocument();
    });
    expect(
      screen.getByRole("heading", { name: /Needs your attention/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Recent Runs/i }),
    ).toBeInTheDocument();
  });

  it("renders KPI numbers from mock data (populated)", async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByTestId("kpi-active-runs")).toHaveTextContent("2");
    });
    expect(screen.getByTestId("kpi-pending-escalations")).toHaveTextContent(
      "1",
    );
    expect(screen.getByTestId("kpi-mini-app-events")).toHaveTextContent("14");
  });

  it("renders Escalation rows from mock data", async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("Business Loan #LOAN-204")).toBeInTheDocument();
    });
  });

  it("renders Recent Run rows from mock data", async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText("Business Loan Pre-Screen")).toBeInTheDocument();
    });
  });

  it("renders empty states when mock mode = empty", async () => {
    __setDashboardMockMode("empty");
    renderDashboard();
    await waitFor(() => {
      expect(screen.getAllByTestId("vaic-empty-state").length).toBeGreaterThan(
        0,
      );
    });
  });

  it("renders error states when mock mode = error", async () => {
    __setDashboardMockMode("error");
    renderDashboard();
    await waitFor(() => {
      expect(screen.getAllByTestId("vaic-error-state").length).toBeGreaterThan(
        0,
      );
    });
  });
});
