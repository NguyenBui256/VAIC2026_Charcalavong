/* Test: DefinitionTab (AC6) — required markers, blur validation, dirty
 * tracking, constraints chip-list, Save success/failure.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../ui";
import DefinitionTab from "./DefinitionTab";
import type { Workflow } from "../../lib/workflowsApi";

const mockUpdateWorkflow = vi.fn();
const mockCreateWorkflow = vi.fn();
vi.mock("../../lib/workflowsApi", async () => {
  const actual = await vi.importActual<typeof import("../../lib/workflowsApi")>(
    "../../lib/workflowsApi",
  );
  return {
    ...actual,
    updateWorkflow: (...args: unknown[]) => mockUpdateWorkflow(...args),
    createWorkflow: (...args: unknown[]) => mockCreateWorkflow(...args),
  };
});

const baseWorkflow: Workflow = {
  id: "workflow-1",
  tenant_id: "tenant-1",
  owner_id: "user-1",
  name: "Loan Intake",
  description: "Handle inbound loan requests.",
  constraints: ["must check credit score"],
  confidence_threshold: 0.7,
  escalation_timeout_seconds: 300,
  version: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderDefinitionTab(overrides: Partial<Parameters<typeof DefinitionTab>[0]> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const onDirtyChange = vi.fn();
  const utils = render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <DefinitionTab
          workflowId="workflow-1"
          isNew={false}
          workflow={baseWorkflow}
          onDirtyChange={onDirtyChange}
          {...overrides}
        />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { ...utils, onDirtyChange };
}

describe("DefinitionTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders required markers on Name and Description only", () => {
    renderDefinitionTab();
    const markers = document.querySelectorAll(".vaic-form-required");
    expect(markers.length).toBe(2);
  });

  it("does not validate Name on keystroke, only on blur", () => {
    renderDefinitionTab();
    const nameInput = screen.getByLabelText("Name", { exact: false }) as HTMLInputElement;
    fireEvent.change(nameInput, { target: { value: "" } });
    expect(screen.queryByText("Name is required")).not.toBeInTheDocument();
    fireEvent.blur(nameInput);
    expect(screen.getByText("Name is required")).toBeInTheDocument();
  });

  it("shows inline error on blur when Description is cleared", () => {
    renderDefinitionTab();
    const textarea = screen.getByLabelText("Description", { exact: false });
    fireEvent.change(textarea, { target: { value: "" } });
    expect(screen.queryByText("Description is required")).not.toBeInTheDocument();
    fireEvent.blur(textarea);
    expect(screen.getByText("Description is required")).toBeInTheDocument();
  });

  it("calls onDirtyChange(true) after editing a field, false when reverted", () => {
    const { onDirtyChange } = renderDefinitionTab();
    const nameInput = screen.getByLabelText("Name", { exact: false });
    fireEvent.change(nameInput, { target: { value: "Loan Intake v2" } });
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
    fireEvent.change(nameInput, { target: { value: "Loan Intake" } });
    expect(onDirtyChange).toHaveBeenLastCalledWith(false);
  });

  it("renders existing constraints as chips and supports adding/removing", () => {
    const { onDirtyChange } = renderDefinitionTab();
    expect(screen.getByText("must check credit score")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("e.g. must check credit score"), {
      target: { value: "must verify identity" },
    });
    fireEvent.click(screen.getByText("Add"));
    expect(screen.getByText("must verify identity")).toBeInTheDocument();
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);

    fireEvent.click(screen.getByLabelText("Remove constraint: must verify identity"));
    expect(screen.queryByText("must verify identity")).not.toBeInTheDocument();
  });

  it("Save fires updateWorkflow and shows a success toast", async () => {
    mockUpdateWorkflow.mockResolvedValueOnce({ ...baseWorkflow, name: "Loan Intake v2" });
    renderDefinitionTab();
    fireEvent.change(screen.getByLabelText("Name", { exact: false }), {
      target: { value: "Loan Intake v2" },
    });
    fireEvent.click(screen.getByText("Save"));

    await waitFor(() =>
      expect(mockUpdateWorkflow).toHaveBeenCalledWith("workflow-1", {
        name: "Loan Intake v2",
        description: "Handle inbound loan requests.",
        constraints: ["must check credit score"],
      }),
    );
    await waitFor(() => expect(screen.getByText("Workflow saved")).toBeInTheDocument());
  });

  it("Save failure shows an inline error", async () => {
    mockUpdateWorkflow.mockRejectedValueOnce(new Error("Name already in use"));
    renderDefinitionTab();
    fireEvent.change(screen.getByLabelText("Name", { exact: false }), {
      target: { value: "Dup Name" },
    });
    fireEvent.click(screen.getByText("Save"));

    await waitFor(() =>
      expect(screen.getByTestId("vaic-definition-save-error")).toHaveTextContent(
        "Name already in use",
      ),
    );
  });

  it("Save is blocked and shows all inline errors when required fields are empty", () => {
    renderDefinitionTab({ workflow: undefined, isNew: true });
    fireEvent.click(screen.getByText("Save"));
    expect(screen.getByText("Name is required")).toBeInTheDocument();
    expect(screen.getByText("Description is required")).toBeInTheDocument();
    expect(mockCreateWorkflow).not.toHaveBeenCalled();
  });
});
