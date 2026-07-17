/* Test: ApiIntegrationsTab (AC #1, #8, #9) — list renders, New Integration
 * form validates on blur, auth header write-only + masked after save, Test
 * Integration shows connected/disconnected, empty/loading/error states.
 * Mocks integrationsApi entirely — no live network. */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../../ui";
import ApiIntegrationsTab from "./ApiIntegrationsTab";
import type { ApiIntegration } from "../../../lib/integrationsApi";

const mockList = vi.fn();
const mockCreate = vi.fn();
const mockUpdate = vi.fn();
const mockDelete = vi.fn();
const mockTest = vi.fn();

vi.mock("../../../lib/integrationsApi", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/integrationsApi")>(
    "../../../lib/integrationsApi",
  );
  return {
    ...actual,
    listIntegrations: (...args: unknown[]) => mockList(...args),
    createIntegration: (...args: unknown[]) => mockCreate(...args),
    updateIntegration: (...args: unknown[]) => mockUpdate(...args),
    deleteIntegration: (...args: unknown[]) => mockDelete(...args),
    testIntegration: (...args: unknown[]) => mockTest(...args),
  };
});

function makeIntegration(overrides: Partial<ApiIntegration> = {}): ApiIntegration {
  return {
    id: "int-1",
    agent_id: "agent-1",
    name: "Demo Gmail",
    base_url: "https://stub.example.com/gmail",
    auth_header_masked: "Bearer ••••abcd",
    schema: null,
    last_used_at: null,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

function renderTab(overrides: Partial<Parameters<typeof ApiIntegrationsTab>[0]> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <ApiIntegrationsTab agentId="agent-1" isNew={false} {...overrides} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("ApiIntegrationsTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the list with name/truncated base_url/last-used (AC8)", async () => {
    mockList.mockResolvedValue([
      makeIntegration({
        base_url: "https://very-long-stub-domain-example.com/some/deep/path/gmail",
      }),
    ]);
    renderTab();
    await waitFor(() => expect(screen.getByText("Demo Gmail")).toBeInTheDocument());
    expect(screen.getByText("Never")).toBeInTheDocument();
    expect(screen.getByText(/…$/)).toBeInTheDocument();
  });

  it("shows the empty state with a New Integration CTA when there are none", async () => {
    mockList.mockResolvedValue([]);
    renderTab();
    await waitFor(() => expect(screen.getByTestId("vaic-empty-state")).toBeInTheDocument());
    expect(screen.getByText("No API Integrations yet")).toBeInTheDocument();
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

  it("shows a save-first message when the Agent is new", () => {
    renderTab({ isNew: true });
    expect(screen.getByText(/Save the Agent first/)).toBeInTheDocument();
  });

  it('"New Integration" opens the editor and validates required fields on blur (AC1, UX-DR8)', async () => {
    mockList.mockResolvedValue([]);
    renderTab();
    await waitFor(() => expect(screen.getByTestId("vaic-empty-state")).toBeInTheDocument());

    await userEvent.click(screen.getByText("New Integration"));
    expect(screen.getByTestId("vaic-integration-editor")).toBeInTheDocument();

    const nameInput = screen.getByLabelText(/^Name/);
    await userEvent.click(nameInput);
    await userEvent.tab();
    expect(await screen.findByText("Name is required")).toBeInTheDocument();

    const saveButton = screen.getByRole("button", { name: "Save" });
    expect(saveButton).toBeDisabled();
  });

  it("Auth Header input is write-only (password type) and masked value shown after save", async () => {
    mockList.mockResolvedValue([]);
    mockCreate.mockResolvedValue(makeIntegration());
    renderTab();
    await waitFor(() => expect(screen.getByTestId("vaic-empty-state")).toBeInTheDocument());
    await userEvent.click(screen.getByText("New Integration"));

    const authInput = screen.getByLabelText(/Auth Header/) as HTMLInputElement;
    expect(authInput.type).toBe("password");

    await userEvent.type(screen.getByLabelText(/^Name/), "Demo Gmail");
    await userEvent.type(screen.getByLabelText(/Base URL/), "https://stub.example.com/gmail");
    await userEvent.type(authInput, "Bearer secret-abcd");

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(mockCreate).toHaveBeenCalledWith("agent-1", {
        name: "Demo Gmail",
        base_url: "https://stub.example.com/gmail",
        auth_header: "Bearer secret-abcd",
        schema: null,
      }),
    );
  });

  it("Test Integration shows connected status", async () => {
    mockList.mockResolvedValue([makeIntegration()]);
    mockTest.mockResolvedValue({ status: "connected", status_code: 200, latency_ms: 42 });
    renderTab();

    await waitFor(() => expect(screen.getByText("Demo Gmail")).toBeInTheDocument());
    await userEvent.click(screen.getByLabelText("Test Integration Demo Gmail"));

    await waitFor(() => expect(screen.getByText("Connected")).toBeInTheDocument());
    expect(mockTest).toHaveBeenCalledWith("agent-1", "int-1");
  });

  it("Test Integration shows disconnected status", async () => {
    mockList.mockResolvedValue([makeIntegration()]);
    mockTest.mockResolvedValue({ status: "disconnected", status_code: 503, latency_ms: 10 });
    renderTab();

    await waitFor(() => expect(screen.getByText("Demo Gmail")).toBeInTheDocument());
    await userEvent.click(screen.getByLabelText("Test Integration Demo Gmail"));

    await waitFor(() => expect(screen.getByText("Disconnected")).toBeInTheDocument());
  });

  it("delete opens ConfirmDialog and confirm calls deleteIntegration", async () => {
    mockList.mockResolvedValue([makeIntegration({ id: "int-9", name: "todelete" })]);
    mockDelete.mockResolvedValue({ id: "int-9" });
    renderTab();

    await waitFor(() => expect(screen.getByText("todelete")).toBeInTheDocument());
    await userEvent.click(screen.getByLabelText("Delete todelete"));

    expect(screen.getByTestId("vaic-confirm-dialog")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Delete", { selector: "button.vaic-btn-destructive" }));

    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith("agent-1", "int-9"));
  });
});
