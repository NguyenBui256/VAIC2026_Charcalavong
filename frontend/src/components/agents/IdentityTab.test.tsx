/* Test: IdentityTab (AC #7, #8, #9, #10) — required markers, blur validation,
 * dirty tracking, Save success/failure.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../ui";
import IdentityTab from "./IdentityTab";
import type { Agent } from "../../lib/agentsApi";

vi.mock("../../lib/departmentsApi", () => ({
  listDepartments: vi.fn(() =>
    Promise.resolve([
      { id: "dept-1", name: "Retail Lending" },
      { id: "dept-2", name: "Risk" },
    ]),
  ),
}));

const mockUpdateAgent = vi.fn();
const mockCreateAgent = vi.fn();
vi.mock("../../lib/agentsApi", async () => {
  const actual = await vi.importActual<typeof import("../../lib/agentsApi")>(
    "../../lib/agentsApi",
  );
  return {
    ...actual,
    updateAgent: (...args: unknown[]) => mockUpdateAgent(...args),
    createAgent: (...args: unknown[]) => mockCreateAgent(...args),
  };
});

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

function renderIdentityTab(overrides: Partial<Parameters<typeof IdentityTab>[0]> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const onDirtyChange = vi.fn();
  const utils = render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <IdentityTab
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

describe("IdentityTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders required markers on Name, Department, System Prompt", async () => {
    renderIdentityTab();
    await waitFor(() => expect(screen.getByText("Retail Lending")).toBeInTheDocument());
    const markers = document.querySelectorAll(".vaic-form-required");
    expect(markers.length).toBe(3);
  });

  it("does not validate Name on keystroke, only on blur", () => {
    renderIdentityTab();
    const nameInput = screen.getByLabelText("Name", { exact: false }) as HTMLInputElement;
    fireEvent.change(nameInput, { target: { value: "" } });
    expect(screen.queryByText("Name is required")).not.toBeInTheDocument();
    fireEvent.blur(nameInput);
    expect(screen.getByText("Name is required")).toBeInTheDocument();
  });

  it("shows inline error on blur when Department is cleared", async () => {
    renderIdentityTab();
    await waitFor(() => expect(screen.getByText("Retail Lending")).toBeInTheDocument());
    const select = screen.getByLabelText("Department", { exact: false }) as HTMLSelectElement;
    fireEvent.change(select, { target: { value: "" } });
    expect(screen.queryByText("Department is required")).not.toBeInTheDocument();
    fireEvent.blur(select);
    expect(screen.getByText("Department is required")).toBeInTheDocument();
  });

  it("calls onDirtyChange(true) after editing a field, false when reverted", () => {
    const { onDirtyChange } = renderIdentityTab();
    const nameInput = screen.getByLabelText("Name", { exact: false });
    fireEvent.change(nameInput, { target: { value: "Loan Screener v2" } });
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
    fireEvent.change(nameInput, { target: { value: "Loan Screener" } });
    expect(onDirtyChange).toHaveBeenLastCalledWith(false);
  });

  it("Save fires updateAgent and shows a success toast", async () => {
    mockUpdateAgent.mockResolvedValueOnce({ ...baseAgent, name: "Loan Screener v2" });
    renderIdentityTab();
    const nameInput = screen.getByLabelText("Name", { exact: false });
    fireEvent.change(nameInput, { target: { value: "Loan Screener v2" } });
    fireEvent.click(screen.getByText("Save"));

    await waitFor(() => expect(mockUpdateAgent).toHaveBeenCalledWith("agent-1", {
      name: "Loan Screener v2",
      department_id: "dept-1",
      system_prompt: "You screen loan applications.",
      status: "draft",
    }));
    await waitFor(() => expect(screen.getByText("Agent saved")).toBeInTheDocument());
  });

  it("Save failure shows an inline error", async () => {
    mockUpdateAgent.mockRejectedValueOnce(new Error("Name already in use"));
    renderIdentityTab();
    fireEvent.change(screen.getByLabelText("Name", { exact: false }), { target: { value: "Dup Name" } });
    fireEvent.click(screen.getByText("Save"));

    await waitFor(() =>
      expect(screen.getByTestId("vaic-identity-save-error")).toHaveTextContent(
        "Name already in use",
      ),
    );
  });

  it("Save is blocked and shows all inline errors when required fields are empty", () => {
    renderIdentityTab({ agent: undefined, isNew: true });
    fireEvent.click(screen.getByText("Save"));
    expect(screen.getByText("Name is required")).toBeInTheDocument();
    expect(screen.getByText("Department is required")).toBeInTheDocument();
    expect(screen.getByText("System prompt is required")).toBeInTheDocument();
    expect(mockCreateAgent).not.toHaveBeenCalled();
  });
});
