/* Test: WorkflowDetailPage — Definition tab is the default view, unsaved-
 * changes guard blocks Back navigation (AC7), New Workflow flow.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../components/ui";
import WorkflowDetailPage from "./workflow-detail";
import type { Workflow } from "../lib/workflowsApi";

const mockGetWorkflow = vi.fn();
const mockUpdateWorkflow = vi.fn();
vi.mock("../lib/workflowsApi", async () => {
  const actual = await vi.importActual<typeof import("../lib/workflowsApi")>(
    "../lib/workflowsApi",
  );
  return {
    ...actual,
    getWorkflow: (...args: unknown[]) => mockGetWorkflow(...args),
    updateWorkflow: (...args: unknown[]) => mockUpdateWorkflow(...args),
  };
});

const workflow: Workflow = {
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
  updated_at: "2026-01-01T00:00:00Z",
};

function renderDetail(initialPath = "/workflows/workflow-1") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/workflows/:id" element={<WorkflowDetailPage />} />
            <Route
              path="/workflows"
              element={<div data-testid="vaic-workflows-page-stub">Workflows list</div>}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("WorkflowDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetWorkflow.mockResolvedValue(workflow);
  });

  it("renders the Definition tab as the default view", async () => {
    renderDetail();
    await waitFor(() => expect(screen.getByTestId("vaic-definition-tab")).toBeInTheDocument());
    expect(screen.getByLabelText("Name", { exact: false })).toHaveValue("Loan Intake");
  });

  it("shows a loading skeleton while the Workflow is fetching", () => {
    mockGetWorkflow.mockReturnValue(new Promise(() => {}));
    renderDetail();
    expect(screen.getByTestId("vaic-workflow-detail-loading")).toBeInTheDocument();
  });

  it("shows ErrorState with retry when the Workflow fetch fails", async () => {
    mockGetWorkflow.mockRejectedValue(new Error("Not found"));
    renderDetail();
    await waitFor(() => expect(screen.getByTestId("vaic-error-state")).toBeInTheDocument());
    expect(screen.getByText("Not found")).toBeInTheDocument();
  });

  it("blocks Back navigation with a ConfirmDialog when the Definition tab is dirty (AC7)", async () => {
    renderDetail();
    await waitFor(() => expect(screen.getByTestId("vaic-definition-tab")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Name", { exact: false }), {
      target: { value: "Loan Intake v2" },
    });

    fireEvent.click(screen.getByText("Back to Workflows"));
    expect(screen.getByTestId("vaic-confirm-dialog")).toBeInTheDocument();
    expect(screen.queryByTestId("vaic-workflows-page-stub")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Discard"));
    expect(screen.getByTestId("vaic-workflows-page-stub")).toBeInTheDocument();
  });

  it("allows Back navigation without a dialog when not dirty", async () => {
    renderDetail();
    await waitFor(() => expect(screen.getByTestId("vaic-definition-tab")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Back to Workflows"));
    expect(screen.queryByTestId("vaic-confirm-dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("vaic-workflows-page-stub")).toBeInTheDocument();
  });

  it("renders the Definition form directly for the New Workflow flow (id=new)", async () => {
    renderDetail("/workflows/new");
    await waitFor(() => expect(screen.getByTestId("vaic-definition-tab")).toBeInTheDocument());
    expect(mockGetWorkflow).not.toHaveBeenCalled();
  });
});
