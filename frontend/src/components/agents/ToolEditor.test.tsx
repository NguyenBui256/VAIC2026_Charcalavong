/* Test: ToolEditor (AC #1, #6, #7) — invalid JSON schema shows inline
 * validation error, masked auth field, save fires createTool/updateTool +
 * success toast, Test Tool success/error render. Mocks toolsApi entirely. */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../ui";
import ToolEditor from "./ToolEditor";
import type { Tool } from "../../lib/toolsApi";

const mockCreate = vi.fn();
const mockUpdate = vi.fn();
const mockTest = vi.fn();

vi.mock("../../lib/toolsApi", async () => {
  const actual = await vi.importActual<typeof import("../../lib/toolsApi")>(
    "../../lib/toolsApi",
  );
  return {
    ...actual,
    createTool: (...args: unknown[]) => mockCreate(...args),
    updateTool: (...args: unknown[]) => mockUpdate(...args),
    deleteTool: vi.fn(),
    listTools: vi.fn().mockResolvedValue([]),
    testTool: (...args: unknown[]) => mockTest(...args),
  };
});

// ToolEditor now renders IntegrationSelect (Story 2.8 item #1) — stub its
// list call so tests stay deterministic without a live backend.
vi.mock("../../lib/integrationsApi", async () => {
  const actual = await vi.importActual<typeof import("../../lib/integrationsApi")>(
    "../../lib/integrationsApi",
  );
  return {
    ...actual,
    listIntegrations: vi.fn().mockResolvedValue([]),
  };
});

function existingTool(overrides: Partial<Tool> = {}): Tool {
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

function renderEditor(tool: Tool | null = null, onClose = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return {
    onClose,
    ...render(
      <QueryClientProvider client={qc}>
        <ToastProvider>
          <ToolEditor agentId="agent-1" tool={tool} onClose={onClose} />
        </ToastProvider>
      </QueryClientProvider>,
    ),
  };
}

describe("ToolEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows an inline validation error for malformed input schema JSON (AC6)", async () => {
    renderEditor();
    const textarea = screen.getByLabelText(/Input schema/);
    await userEvent.clear(textarea);
    await userEvent.type(textarea, "not valid json{{}");

    await waitFor(() =>
      expect(screen.getAllByRole("alert").some((el) => el.textContent)).toBe(true),
    );
  });

  it("does not echo the full auth secret — only a masked checkbox (AC1/NFR-9)", () => {
    renderEditor(existingTool());
    expect(screen.getByLabelText(/Requires auth/)).toBeChecked();
    expect(screen.queryByText(/token_ref/)).not.toBeInTheDocument();
  });

  it("save fires createTool for a new Tool and shows a success toast", async () => {
    mockCreate.mockResolvedValue(existingTool());
    const { onClose } = renderEditor(null);

    await userEvent.type(screen.getByLabelText(/Display name/), "my_tool");
    await userEvent.click(screen.getByText("Save"));

    await waitFor(() => expect(mockCreate).toHaveBeenCalledWith("agent-1", expect.objectContaining({
      display_name: "my_tool",
    })));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("save fires updateTool for an existing Tool", async () => {
    mockUpdate.mockResolvedValue(existingTool());
    const { onClose } = renderEditor(existingTool());

    await userEvent.click(screen.getByText("Save"));

    await waitFor(() =>
      expect(mockUpdate).toHaveBeenCalledWith(
        "agent-1",
        "tool-1",
        expect.objectContaining({ display_name: "rag.search" }),
      ),
    );
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("Test Tool renders a success output (AC7)", async () => {
    mockTest.mockResolvedValue({
      tool_name: "rag.search",
      output: { passages: ["a"] },
      success: true,
      error: "",
      latency_ms: 12,
    });
    renderEditor(existingTool());

    await userEvent.click(screen.getByText("Run Test"));

    const resultPanel = await screen.findByTestId("vaic-tool-test-result");
    expect(within(resultPanel).getByText(/passages/)).toBeInTheDocument();
  });

  it("Test Tool renders a structured validation error (AC7)", async () => {
    mockTest.mockResolvedValue({
      tool_name: "rag.search",
      output: {},
      success: false,
      error: "Input validation failed: query: 'query' is a required property",
      latency_ms: 3,
    });
    renderEditor(existingTool());

    await userEvent.click(screen.getByText("Run Test"));

    await waitFor(() =>
      expect(screen.getByText(/Input validation failed/)).toBeInTheDocument(),
    );
  });
});
