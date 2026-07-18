/* Test: ModelTab (AC #1, #2, #3, #4, #5) — provider disable, model
 * repopulation, params, save payload shape. */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../../ui";
import ModelTab from "./ModelTab";
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
    models: [
      { name: "claude-sonnet-4-5", context_window: 200_000 },
      { name: "claude-opus-4-1", context_window: 200_000 },
    ],
  },
  { id: "openai", label: "OpenAI", configured: false, models: [] },
  { id: "google", label: "Google", configured: false, models: [] },
  { id: "ollama", label: "Ollama", configured: false, models: [] },
];

const baseAgent: Agent = {
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

function renderModelTab(overrides: Partial<Parameters<typeof ModelTab>[0]> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const onDirtyChange = vi.fn();
  const utils = render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <ModelTab
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

describe("ModelTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListProviders.mockResolvedValue(catalog);
  });

  it("disables unconfigured providers with a 'Not configured' label (AC1)", async () => {
    renderModelTab();
    await waitFor(() => expect(screen.getByText("Anthropic")).toBeInTheDocument());

    const select = screen.getByLabelText("Provider") as HTMLSelectElement;
    const options = Array.from(select.options);
    const anthropicOpt = options.find((o) => o.value === "anthropic")!;
    const openaiOpt = options.find((o) => o.value === "openai")!;

    expect(anthropicOpt.disabled).toBe(false);
    expect(openaiOpt.disabled).toBe(true);
    expect(openaiOpt.textContent).toContain("Not configured");
  });

  it("repopulates the Model dropdown when the Provider changes (AC2)", async () => {
    renderModelTab();
    await waitFor(() => expect(screen.getByText("Anthropic")).toBeInTheDocument());

    const providerSelect = screen.getByLabelText("Provider") as HTMLSelectElement;
    fireEvent.change(providerSelect, { target: { value: "anthropic" } });

    const modelSelect = screen.getByLabelText("Model") as HTMLSelectElement;
    const modelOptions = Array.from(modelSelect.options).map((o) => o.value);
    expect(modelOptions).toContain("claude-sonnet-4-5");
    expect(modelOptions).toContain("claude-opus-4-1");
  });

  it("Save posts {provider, model_name, parameters} with only set params (AC3, AC4)", async () => {
    mockUpdateAgent.mockResolvedValueOnce({
      ...baseAgent,
      model: { provider: "anthropic", model_name: "claude-sonnet-4-5", parameters: { max_tokens: 2048 } },
    });
    renderModelTab();
    await waitFor(() => expect(screen.getByText("Anthropic")).toBeInTheDocument());

    // Existing Agent starts in view mode — enter edit mode before mutating.
    fireEvent.click(screen.getByTestId("vaic-tab-edit"));
    fireEvent.change(screen.getByLabelText("Provider"), { target: { value: "anthropic" } });
    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "claude-sonnet-4-5" } });
    fireEvent.change(screen.getByLabelText(/Max tokens/), { target: { value: "2048" } });
    fireEvent.click(screen.getByTestId("vaic-tab-save"));

    await waitFor(() =>
      expect(mockUpdateAgent).toHaveBeenCalledWith("agent-1", {
        model: {
          provider: "anthropic",
          model_name: "claude-sonnet-4-5",
          parameters: { max_tokens: 2048 },
        },
      }),
    );
    await waitFor(() => expect(screen.getByText("Agent saved")).toBeInTheDocument());
  });

  it("marks dirty when provider/model selection changes", async () => {
    const { onDirtyChange } = renderModelTab();
    await waitFor(() => expect(screen.getByText("Anthropic")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Provider"), { target: { value: "anthropic" } });
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
  });
});
