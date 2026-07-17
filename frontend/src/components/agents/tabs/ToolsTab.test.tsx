/* Test: ToolsTab (AC #1, #6, #7) — list renders, empty/loading/error states,
 * "New Tool" opens editor. Mocks toolsApi entirely — no live network. */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../../ui";
import ToolsTab from "./ToolsTab";
import type { Tool } from "../../../lib/toolsApi";

const mockList = vi.fn();
const mockCreate = vi.fn();
const mockUpdate = vi.fn();
const mockDelete = vi.fn();
const mockTest = vi.fn();

vi.mock("../../../lib/toolsApi", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/toolsApi")>(
    "../../../lib/toolsApi",
  );
  return {
    ...actual,
    listTools: (...args: unknown[]) => mockList(...args),
    createTool: (...args: unknown[]) => mockCreate(...args),
    updateTool: (...args: unknown[]) => mockUpdate(...args),
    deleteTool: (...args: unknown[]) => mockDelete(...args),
    testTool: (...args: unknown[]) => mockTest(...args),
  };
});

// ToolEditor (mounted when "New Tool"/Edit is clicked) now renders
// IntegrationSelect (Story 2.8 item #1) — stub its list call.
vi.mock("../../../lib/integrationsApi", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/integrationsApi")>(
    "../../../lib/integrationsApi",
  );
  return {
    ...actual,
    listIntegrations: vi.fn().mockResolvedValue([]),
  };
});

function makeTool(overrides: Partial<Tool> = {}): Tool {
  return {
    id: "tool-1",
    agent_id: "agent-1",
    display_name: "rag.search",
    header: { auth: true },
    input_schema: { type: "object", properties: { query: { type: "string" } } },
    output_schema: { type: "object", properties: { passages: { type: "array" } } },
    has_embedded_python: false,
    kind: "mcp",
    integration_id: null,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

function renderTab(overrides: Partial<Parameters<typeof ToolsTab>[0]> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <ToolsTab agentId="agent-1" isNew={false} {...overrides} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("ToolsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the list with Tool rows (AC1)", async () => {
    mockList.mockResolvedValue([makeTool({ display_name: "rag.search" })]);
    renderTab();
    await waitFor(() => expect(screen.getByText("rag.search")).toBeInTheDocument());
    expect(screen.getByText("MCP")).toBeInTheDocument();
  });

  it("shows the empty state with a New Tool CTA when there are no Tools", async () => {
    mockList.mockResolvedValue([]);
    renderTab();
    await waitFor(() => expect(screen.getByTestId("vaic-empty-state")).toBeInTheDocument());
    expect(screen.getByText("No Tools yet")).toBeInTheDocument();
  });

  it("shows an error state with retry on load failure", async () => {
    mockList.mockRejectedValue(new Error("network down"));
    renderTab();
    await waitFor(() => expect(screen.getByTestId("vaic-error-state")).toBeInTheDocument());
    expect(screen.getByText("network down")).toBeInTheDocument();
  });

  it("shows a loading skeleton while fetching", async () => {
    mockList.mockReturnValue(new Promise(() => {}));
    renderTab();
    expect(screen.getByTestId("vaic-skeleton")).toBeInTheDocument();
  });

  it('"New Tool" opens the editor (AC1)', async () => {
    mockList.mockResolvedValue([]);
    renderTab();
    await waitFor(() => expect(screen.getByTestId("vaic-empty-state")).toBeInTheDocument());

    await userEvent.click(screen.getByText("New Tool"));
    expect(screen.getByTestId("vaic-tool-editor")).toBeInTheDocument();
  });

  it("delete opens ConfirmDialog and confirm calls deleteTool", async () => {
    mockList.mockResolvedValue([makeTool({ id: "t9", display_name: "todelete" })]);
    mockDelete.mockResolvedValue({ id: "t9" });
    renderTab();

    await waitFor(() => expect(screen.getByText("todelete")).toBeInTheDocument());
    await userEvent.click(screen.getByLabelText("Delete todelete"));

    expect(screen.getByTestId("vaic-confirm-dialog")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Delete", { selector: "button.vaic-btn-destructive" }));

    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith("agent-1", "t9"));
  });

  it("shows a save-first message when the Agent is new", () => {
    renderTab({ isNew: true });
    expect(screen.getByText(/Save the Agent first/)).toBeInTheDocument();
  });
});
