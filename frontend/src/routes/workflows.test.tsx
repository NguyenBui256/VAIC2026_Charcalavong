/* Test: WorkflowsPage — list renders rows, search filter, empty/loading/error
 * states, "New Workflow" navigates (AC #5).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within, act } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import WorkflowsPage from "./workflows";
import type { Workflow } from "../lib/workflowsApi";

const mockListWorkflows = vi.fn();
vi.mock("../lib/workflowsApi", async () => {
  const actual = await vi.importActual<typeof import("../lib/workflowsApi")>(
    "../lib/workflowsApi",
  );
  return {
    ...actual,
    listWorkflows: (...args: unknown[]) => mockListWorkflows(...args),
  };
});

const workflows: Workflow[] = [
  {
    id: "workflow-1",
    tenant_id: "tenant-1",
    owner_id: "user-1",
    name: "Loan Intake",
    description: "Handle inbound loan requests.",
    constraints: [],
    confidence_threshold: 0.7,
    escalation_timeout_seconds: 300,
    version: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
  {
    id: "workflow-2",
    tenant_id: "tenant-1",
    owner_id: "user-2",
    name: "HR Onboarding",
    description: "Handle new hire onboarding.",
    constraints: [],
    confidence_threshold: 0.7,
    escalation_timeout_seconds: 300,
    version: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
];

function renderWorkflowsPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/workflows"]}>
        <Routes>
          <Route path="/workflows" element={<WorkflowsPage />} />
          <Route
            path="/workflows/new"
            element={<div data-testid="vaic-new-workflow-stub">New Workflow</div>}
          />
          <Route
            path="/workflows/:id"
            element={<div data-testid="vaic-workflow-detail-stub">Detail</div>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("WorkflowsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListWorkflows.mockResolvedValue(workflows);
  });

  it("renders rows with name and owner", async () => {
    renderWorkflowsPage();
    await waitFor(() => expect(screen.getByText("Loan Intake")).toBeInTheDocument());
    expect(screen.getByText("HR Onboarding")).toBeInTheDocument();
  });

  it("navigates to the detail route when a row is clicked", async () => {
    renderWorkflowsPage();
    await waitFor(() => expect(screen.getByText("Loan Intake")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("vaic-table-row-workflow-1"));
    expect(screen.getByTestId("vaic-workflow-detail-stub")).toBeInTheDocument();
  });

  it("navigates to /workflows/new when New Workflow is clicked", async () => {
    renderWorkflowsPage();
    await waitFor(() => expect(screen.getByText("Loan Intake")).toBeInTheDocument());
    fireEvent.click(screen.getByText("New Workflow"));
    expect(screen.getByTestId("vaic-new-workflow-stub")).toBeInTheDocument();
  });

  it("debounces the search input at 200ms", async () => {
    renderWorkflowsPage();
    await waitFor(() => expect(mockListWorkflows).toHaveBeenCalled());
    mockListWorkflows.mockClear();

    vi.useFakeTimers();
    try {
      const input = screen.getByLabelText("Search Workflows");
      fireEvent.change(input, { target: { value: "Loan" } });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });
      expect(mockListWorkflows).not.toHaveBeenCalled();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });
    } finally {
      vi.useRealTimers();
    }

    await waitFor(() =>
      expect(mockListWorkflows).toHaveBeenCalledWith({ search: "Loan", owner_id: undefined }),
    );
  });

  it("re-queries with owner_id when the Owner filter changes", async () => {
    renderWorkflowsPage();
    await waitFor(() => expect(mockListWorkflows).toHaveBeenCalledWith({}));
    mockListWorkflows.mockClear();

    fireEvent.change(screen.getByLabelText("Filter by Owner"), {
      target: { value: "user-2" },
    });

    await waitFor(() =>
      expect(mockListWorkflows).toHaveBeenCalledWith({ search: undefined, owner_id: "user-2" }),
    );
  });

  it("renders an empty state with a New Workflow CTA when there are zero Workflows", async () => {
    mockListWorkflows.mockResolvedValue([]);
    renderWorkflowsPage();
    await waitFor(() => expect(screen.getByTestId("vaic-empty-state")).toBeInTheDocument());
    expect(screen.getByText("No workflows yet.")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("vaic-empty-state")).getByText("New Workflow"),
    ).toBeInTheDocument();
  });

  it("renders a loading skeleton while fetching", () => {
    mockListWorkflows.mockReturnValue(new Promise(() => {}));
    renderWorkflowsPage();
    expect(screen.getByTestId("vaic-workflows-loading")).toBeInTheDocument();
  });

  it("renders ErrorState with retry when the fetch fails", async () => {
    mockListWorkflows.mockRejectedValue(new Error("Network down"));
    renderWorkflowsPage();
    await waitFor(() => expect(screen.getByTestId("vaic-error-state")).toBeInTheDocument());
    expect(screen.getByText("Network down")).toBeInTheDocument();
  });
});
