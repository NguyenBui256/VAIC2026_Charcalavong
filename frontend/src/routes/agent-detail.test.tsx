/* Test: AgentDetailPage — 6 tabs present, Identity is default, tab switching,
 * placeholder panels render, unsaved-changes guard blocks Back navigation.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../components/ui";
import AgentDetailPage from "./agent-detail";
import type { Agent } from "../lib/agentsApi";

vi.mock("../lib/departmentsApi", () => ({
  listDepartments: vi.fn(() => Promise.resolve([{ id: "dept-1", name: "Retail Lending" }])),
}));

const mockGetAgent = vi.fn();
const mockUpdateAgent = vi.fn();
vi.mock("../lib/agentsApi", async () => {
  const actual = await vi.importActual<typeof import("../lib/agentsApi")>("../lib/agentsApi");
  return {
    ...actual,
    getAgent: (...args: unknown[]) => mockGetAgent(...args),
    updateAgent: (...args: unknown[]) => mockUpdateAgent(...args),
  };
});

const mockListKbDocuments = vi.fn();
vi.mock("../lib/kbApi", async () => {
  const actual = await vi.importActual<typeof import("../lib/kbApi")>("../lib/kbApi");
  return {
    ...actual,
    listKbDocuments: (...args: unknown[]) => mockListKbDocuments(...args),
  };
});

const agent: Agent = {
  id: "agent-1",
  tenant_id: "tenant-1",
  department_id: "dept-1",
  owner_id: "user-1",
  name: "Loan Screener",
  system_prompt: "You screen loan applications.",
  model: {},
  status: "draft",
  version: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderDetail(initialPath = "/agents/agent-1") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/agents/:id" element={<AgentDetailPage />} />
            <Route path="/agents" element={<div data-testid="vaic-agents-page-stub">Agents list</div>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("AgentDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetAgent.mockResolvedValue(agent);
    mockListKbDocuments.mockResolvedValue([]);
  });

  it("renders all 6 tabs with Identity as the default active tab", async () => {
    renderDetail();
    await waitFor(() => expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument());

    expect(screen.getByTestId("vaic-tab-identity")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("vaic-tab-knowledge-base")).toBeInTheDocument();
    expect(screen.getByTestId("vaic-tab-tools")).toBeInTheDocument();
    expect(screen.getByTestId("vaic-tab-api-integrations")).toBeInTheDocument();
    expect(screen.getByTestId("vaic-tab-prompt")).toBeInTheDocument();
    expect(screen.getByTestId("vaic-tab-model")).toBeInTheDocument();
  });

  it("switches to the Knowledge Base tab on click", async () => {
    renderDetail();
    await waitFor(() => expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("vaic-tab-knowledge-base"));

    await waitFor(() =>
      expect(screen.getByTestId("vaic-kb-nfr9-advisory")).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("vaic-identity-tab")).not.toBeInTheDocument();
  });

  it("shows a loading skeleton while the Agent is fetching", () => {
    mockGetAgent.mockReturnValue(new Promise(() => {})); // never resolves
    renderDetail();
    expect(screen.getByTestId("vaic-agent-detail-loading")).toBeInTheDocument();
  });

  it("shows ErrorState with retry when the Agent fetch fails", async () => {
    mockGetAgent.mockRejectedValue(new Error("Not found"));
    renderDetail();
    await waitFor(() => expect(screen.getByTestId("vaic-error-state")).toBeInTheDocument());
    expect(screen.getByText("Not found")).toBeInTheDocument();
  });

  it("blocks Back navigation with a ConfirmDialog when the Identity tab is dirty", async () => {
    renderDetail();
    await waitFor(() => expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Name", { exact: false }), {
      target: { value: "Loan Screener v2" },
    });
    expect(screen.getByTestId("vaic-dirty-dot")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Back to Agents"));
    expect(screen.getByTestId("vaic-confirm-dialog")).toBeInTheDocument();
    expect(screen.queryByTestId("vaic-agents-page-stub")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Discard"));
    expect(screen.getByTestId("vaic-agents-page-stub")).toBeInTheDocument();
  });

  it("allows Back navigation without a dialog when not dirty", async () => {
    renderDetail();
    await waitFor(() => expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Back to Agents"));
    expect(screen.queryByTestId("vaic-confirm-dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("vaic-agents-page-stub")).toBeInTheDocument();
  });

  it("renders the Identity form directly for the New Agent flow (id=new)", async () => {
    renderDetail("/agents/new");
    await waitFor(() => expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument());
    expect(mockGetAgent).not.toHaveBeenCalled();
  });
});
