/* Test: PromptTab (AC #6, #7, #8) — char count, directive highlight,
 * context-window warning, save. */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../../ui";
import PromptTab from "./PromptTab";
import type { Agent, ProviderCatalogEntry } from "../../../lib/agentsApi";

const mockListProviders = vi.fn();
const mockUpdateAgent = vi.fn();
vi.mock("../../../lib/agentsApi", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/agentsApi")>(
    "../../../lib/agentsApi",
  );
  return {
    ...actual,
    listProviders: (...args: unknown[]) => mockListProviders(...args),
    updateAgent: (...args: unknown[]) => mockUpdateAgent(...args),
  };
});

const catalog: ProviderCatalogEntry[] = [
  {
    id: "anthropic",
    label: "Anthropic",
    configured: true,
    models: [{ name: "claude-sonnet-4-5", context_window: 200_000 }],
  },
  { id: "openai", label: "OpenAI", configured: false, models: [] },
];

const baseAgent: Agent = {
  id: "agent-1",
  tenant_id: "tenant-1",
  department_id: "dept-1",
  owner_id: "user-1",
  name: "Loan Screener",
  system_prompt: "You screen loan applications.",
  model: { provider: "anthropic", model_name: "claude-sonnet-4-5", parameters: {} },
  status: "draft",
  version: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderPromptTab(overrides: Partial<Parameters<typeof PromptTab>[0]> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const onDirtyChange = vi.fn();
  const utils = render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <PromptTab
          agentId="agent-1"
          isNew={false}
          agent={baseAgent}
          onDirtyChange={onDirtyChange}
          {...overrides}
        />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { ...utils, onDirtyChange };
}

describe("PromptTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListProviders.mockResolvedValue(catalog);
  });

  it("shows a live character count", () => {
    renderPromptTab();
    expect(screen.getByTestId("vaic-prompt-char-count")).toHaveTextContent(
      String(baseAgent.system_prompt.length),
    );
    fireEvent.change(screen.getByLabelText("System prompt"), {
      target: { value: "short" },
    });
    expect(screen.getByTestId("vaic-prompt-char-count")).toHaveTextContent("5");
  });

  it("highlights {{tool:...}} and {{kb:...}} directive tokens (AC6)", () => {
    renderPromptTab();
    fireEvent.change(screen.getByLabelText("System prompt"), {
      target: { value: "Use {{tool:rag.search}} and {{kb:agent_id}} to answer." },
    });
    const directives = screen.getAllByTestId("vaic-prompt-directive");
    expect(directives.map((d) => d.textContent)).toEqual([
      "{{tool:rag.search}}",
      "{{kb:agent_id}}",
    ]);
  });

  it("shows a non-blocking warning past the model's context window (AC7)", async () => {
    renderPromptTab();
    await waitFor(() => expect(mockListProviders).toHaveBeenCalled());
    // Enter edit mode so the editor + Save button are available.
    fireEvent.click(screen.getByTestId("vaic-tab-edit"));

    expect(screen.queryByTestId("vaic-prompt-context-warning")).not.toBeInTheDocument();

    // context_window = 200_000 tokens; ~4 chars/token => >800_000 chars trips it.
    const huge = "x".repeat(900_000);
    fireEvent.change(screen.getByLabelText("System prompt"), { target: { value: huge } });

    await waitFor(() =>
      expect(screen.getByTestId("vaic-prompt-context-warning")).toBeInTheDocument(),
    );
    // Non-blocking: Save is still enabled.
    expect(screen.getByTestId("vaic-tab-save")).not.toBeDisabled();
  });

  it("Save fires updateAgent with system_prompt and shows a success toast (AC8)", async () => {
    mockUpdateAgent.mockResolvedValueOnce({ ...baseAgent, system_prompt: "New prompt" });
    renderPromptTab();

    fireEvent.click(screen.getByTestId("vaic-tab-edit"));
    fireEvent.change(screen.getByLabelText("System prompt"), {
      target: { value: "New prompt" },
    });
    fireEvent.click(screen.getByTestId("vaic-tab-save"));

    await waitFor(() =>
      expect(mockUpdateAgent).toHaveBeenCalledWith("agent-1", { system_prompt: "New prompt" }),
    );
    await waitFor(() => expect(screen.getByText("Agent saved")).toBeInTheDocument());
  });

  it("Save failure shows an inline error", async () => {
    mockUpdateAgent.mockRejectedValueOnce(new Error("Prompt too long"));
    renderPromptTab();

    fireEvent.click(screen.getByTestId("vaic-tab-edit"));
    fireEvent.change(screen.getByLabelText("System prompt"), { target: { value: "x" } });
    fireEvent.click(screen.getByTestId("vaic-tab-save"));

    await waitFor(() =>
      expect(screen.getByTestId("vaic-prompt-save-error")).toHaveTextContent("Prompt too long"),
    );
  });
});
