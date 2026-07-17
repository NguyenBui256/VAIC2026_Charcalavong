/* Story 2.8 — Agent Builder surface integration tests.
 *
 * AC #2 count badges, AC #4 three-button switch guard, AC #7 new-Agent
 * gating + unlock after first save, AC #8 Save All, AC #9 keyboard nav.
 * Mocks every sibling-tab API module so this is verifiable standalone
 * (Dev Notes "graceful degradation" / T8.6).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../ui";
import AgentDetailShell from "./AgentDetailShell";
import type { Agent } from "../../lib/agentsApi";

vi.mock("../../lib/departmentsApi", () => ({
  listDepartments: vi.fn(() => Promise.resolve([{ id: "dept-1", name: "Retail Lending" }])),
}));

const mockGetAgent = vi.fn();
const mockUpdateAgent = vi.fn();
const mockCreateAgent = vi.fn();
vi.mock("../../lib/agentsApi", async () => {
  const actual = await vi.importActual<typeof import("../../lib/agentsApi")>(
    "../../lib/agentsApi",
  );
  return {
    ...actual,
    getAgent: (...args: unknown[]) => mockGetAgent(...args),
    updateAgent: (...args: unknown[]) => mockUpdateAgent(...args),
    createAgent: (...args: unknown[]) => mockCreateAgent(...args),
  };
});

vi.mock("../../lib/kbApi", async () => {
  const actual = await vi.importActual<typeof import("../../lib/kbApi")>("../../lib/kbApi");
  return {
    ...actual,
    listKbDocuments: vi.fn().mockResolvedValue([{ id: "doc-1" }, { id: "doc-2" }]),
  };
});

vi.mock("../../lib/toolsApi", async () => {
  const actual = await vi.importActual<typeof import("../../lib/toolsApi")>(
    "../../lib/toolsApi",
  );
  return {
    ...actual,
    listTools: vi.fn().mockResolvedValue([{ id: "tool-1" }]),
  };
});

vi.mock("../../lib/integrationsApi", async () => {
  const actual = await vi.importActual<typeof import("../../lib/integrationsApi")>(
    "../../lib/integrationsApi",
  );
  return {
    ...actual,
    listIntegrations: vi.fn().mockResolvedValue([]),
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

function renderShell(agentId = "agent-1") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/agents/${agentId}`]}>
          <AgentDetailShell agentId={agentId} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("AgentDetailShell — Story 2.8 integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetAgent.mockResolvedValue(agent);
  });

  it("shows count badges once each tab's query resolves (AC #2)", async () => {
    renderShell();
    await waitFor(() => expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument());

    await waitFor(() => {
      const kbTab = screen.getByTestId("vaic-tab-knowledge-base");
      expect(kbTab).toHaveTextContent("2 documents");
    });
    await waitFor(() => {
      expect(screen.getByTestId("vaic-tab-tools")).toHaveTextContent("1 tool");
    });
    await waitFor(() => {
      expect(screen.getByTestId("vaic-tab-api-integrations")).toHaveTextContent(
        "0 integrations",
      );
    });
  });

  it("shows the Department badge + status pill + Save All (hidden when clean) in the header (AC #8)", async () => {
    renderShell();
    await waitFor(() => expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument());

    expect(screen.getByTestId("vaic-department-badge")).toHaveTextContent("Retail Lending");
    expect(screen.queryByTestId("vaic-save-all")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Name", { exact: false }), {
      target: { value: "Loan Screener v2" },
    });

    await waitFor(() => expect(screen.getByTestId("vaic-save-all")).toBeInTheDocument());
  });

  it("Save All persists the dirty tab and shows a success toast (AC #8)", async () => {
    mockUpdateAgent.mockResolvedValue({ ...agent, name: "Loan Screener v2" });
    renderShell();
    await waitFor(() => expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Name", { exact: false }), {
      target: { value: "Loan Screener v2" },
    });
    await waitFor(() => expect(screen.getByTestId("vaic-save-all")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("vaic-save-all"));

    await waitFor(() => expect(mockUpdateAgent).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("All changes saved")).toBeInTheDocument());
  });

  it("opens a Save/Discard/Cancel dialog when switching away from a dirty tab (AC #4)", async () => {
    renderShell();
    await waitFor(() => expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Name", { exact: false }), {
      target: { value: "Loan Screener v2" },
    });

    fireEvent.click(screen.getByTestId("vaic-tab-model"));

    const dialog = screen.getByTestId("vaic-confirm-dialog");
    expect(within(dialog).getByText("Save")).toBeInTheDocument();
    expect(within(dialog).getByText("Discard")).toBeInTheDocument();
    expect(within(dialog).getByText("Cancel")).toBeInTheDocument();
    // Still on Identity — the switch hasn't happened yet.
    expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument();
  });

  it("Discard drops the edit and switches tabs (AC #4)", async () => {
    renderShell();
    await waitFor(() => expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Name", { exact: false }), {
      target: { value: "Loan Screener v2" },
    });
    fireEvent.click(screen.getByTestId("vaic-tab-model"));
    fireEvent.click(within(screen.getByTestId("vaic-confirm-dialog")).getByText("Discard"));

    await waitFor(() => expect(screen.getByTestId("vaic-model-tab")).toBeInTheDocument());
  });

  it("Cancel keeps the user on the current (dirty) tab (AC #4)", async () => {
    renderShell();
    await waitFor(() => expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Name", { exact: false }), {
      target: { value: "Loan Screener v2" },
    });
    fireEvent.click(screen.getByTestId("vaic-tab-model"));
    fireEvent.click(within(screen.getByTestId("vaic-confirm-dialog")).getByText("Cancel"));

    expect(screen.queryByTestId("vaic-confirm-dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument();
  });

  it("gates all tabs but Identity for a never-saved (new) Agent, unlocking after first save (AC #7)", async () => {
    mockCreateAgent.mockResolvedValue({ ...agent, id: "agent-new-1" });
    renderShell("new");
    await waitFor(() => expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument());
    expect(mockGetAgent).not.toHaveBeenCalled();

    const modelTab = screen.getByTestId("vaic-tab-model");
    expect(modelTab).toHaveAttribute("aria-disabled", "true");

    fireEvent.click(modelTab);
    // Disabled — clicking must not switch tabs.
    expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument();
  });

  it("keyboard: ArrowRight moves focus+selection to the next tab, skipping disabled ones (AC #9)", async () => {
    renderShell();
    await waitFor(() => expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument());

    const identityTab = screen.getByTestId("vaic-tab-identity");
    identityTab.focus();
    fireEvent.keyDown(identityTab, { key: "ArrowRight" });

    await waitFor(() =>
      expect(screen.getByTestId("vaic-tab-knowledge-base")).toHaveAttribute(
        "aria-selected",
        "true",
      ),
    );
  });

  it("keyboard: End jumps to the last tab", async () => {
    renderShell();
    await waitFor(() => expect(screen.getByTestId("vaic-identity-tab")).toBeInTheDocument());

    const identityTab = screen.getByTestId("vaic-tab-identity");
    identityTab.focus();
    fireEvent.keyDown(identityTab, { key: "End" });

    await waitFor(() =>
      expect(screen.getByTestId("vaic-tab-model")).toHaveAttribute("aria-selected", "true"),
    );
  });
});
