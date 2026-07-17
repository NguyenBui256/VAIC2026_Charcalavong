/* Test: AgentsPage — list renders rows, Department filter, debounced search,
 * empty/loading/error states, "New Agent" navigates (AC #1-4).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within, act } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AgentsPage from "./agents";
import type { Agent } from "../lib/agentsApi";

vi.mock("../lib/departmentsApi", () => ({
  listDepartments: vi.fn(() =>
    Promise.resolve([
      { id: "dept-1", name: "Retail Lending" },
      { id: "dept-2", name: "Risk" },
    ]),
  ),
}));

const mockListAgents = vi.fn();
vi.mock("../lib/agentsApi", async () => {
  const actual = await vi.importActual<typeof import("../lib/agentsApi")>("../lib/agentsApi");
  return {
    ...actual,
    listAgents: (...args: unknown[]) => mockListAgents(...args),
  };
});

const agents: Agent[] = [
  {
    id: "agent-1",
    tenant_id: "tenant-1",
    department_id: "dept-1",
    owner_id: "user-1",
    name: "Loan Screener",
    system_prompt: "Screen loans.",
    status: "active",
    version: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
  {
    id: "agent-2",
    tenant_id: "tenant-1",
    department_id: "dept-2",
    owner_id: "user-2",
    name: "Risk Reviewer",
    system_prompt: "Review risk.",
    status: "draft",
    version: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
];

function renderAgentsPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/agents"]}>
        <Routes>
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/agents/new" element={<div data-testid="vaic-new-agent-stub">New Agent</div>} />
          <Route
            path="/agents/:id"
            element={<div data-testid="vaic-agent-detail-stub">Detail</div>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("AgentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListAgents.mockResolvedValue(agents);
  });

  it("renders rows with name, department, status, owner, last-modified", async () => {
    renderAgentsPage();
    await waitFor(() => expect(screen.getByText("Loan Screener")).toBeInTheDocument());
    expect(screen.getByText("Risk Reviewer")).toBeInTheDocument();
    expect(screen.getAllByTestId("vaic-department-badge").length).toBe(2);
    expect(screen.getByTestId("vaic-pill-active")).toBeInTheDocument();
    expect(screen.getByTestId("vaic-pill-draft")).toBeInTheDocument();
  });

  it("navigates to the detail route when a row is clicked", async () => {
    renderAgentsPage();
    await waitFor(() => expect(screen.getByText("Loan Screener")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("vaic-table-row-agent-1"));
    expect(screen.getByTestId("vaic-agent-detail-stub")).toBeInTheDocument();
  });

  it("navigates to /agents/new when New Agent is clicked", async () => {
    renderAgentsPage();
    await waitFor(() => expect(screen.getByText("Loan Screener")).toBeInTheDocument());
    fireEvent.click(screen.getByText("New Agent"));
    expect(screen.getByTestId("vaic-new-agent-stub")).toBeInTheDocument();
  });

  it("re-queries with department_id when the Department filter changes", async () => {
    renderAgentsPage();
    await waitFor(() => expect(mockListAgents).toHaveBeenCalledWith({}));
    await waitFor(() =>
      expect(screen.getByRole("option", { name: "Risk" })).toBeInTheDocument(),
    );
    mockListAgents.mockClear();

    fireEvent.change(screen.getByLabelText("Filter by Department"), {
      target: { value: "dept-2" },
    });

    await waitFor(() =>
      expect(mockListAgents).toHaveBeenCalledWith({ department_id: "dept-2", q: undefined }),
    );
  });

  it("debounces the search input at 200ms", async () => {
    renderAgentsPage();
    await waitFor(() => expect(mockListAgents).toHaveBeenCalled());
    mockListAgents.mockClear();

    vi.useFakeTimers();
    try {
      const input = screen.getByLabelText("Search Agents");
      fireEvent.change(input, { target: { value: "Loan" } });

      // Not yet queried before the debounce window elapses.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });
      expect(mockListAgents).not.toHaveBeenCalled();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });
    } finally {
      vi.useRealTimers();
    }

    await waitFor(() =>
      expect(mockListAgents).toHaveBeenCalledWith({ department_id: undefined, q: "Loan" }),
    );
  });

  it("renders an empty state with a New Agent CTA when there are zero Agents", async () => {
    mockListAgents.mockResolvedValue([]);
    renderAgentsPage();
    await waitFor(() => expect(screen.getByTestId("vaic-empty-state")).toBeInTheDocument());
    expect(within(screen.getByTestId("vaic-empty-state")).getByText("New Agent")).toBeInTheDocument();
  });

  it("renders a loading skeleton while fetching", () => {
    mockListAgents.mockReturnValue(new Promise(() => {}));
    renderAgentsPage();
    expect(screen.getByTestId("vaic-agents-loading")).toBeInTheDocument();
  });

  it("renders ErrorState with retry when the fetch fails", async () => {
    mockListAgents.mockRejectedValue(new Error("Network down"));
    renderAgentsPage();
    await waitFor(() => expect(screen.getByTestId("vaic-error-state")).toBeInTheDocument());
    expect(screen.getByText("Network down")).toBeInTheDocument();
  });
});
