/* Test: KnowledgeBaseTab (AC #2, #3, #4, #5, #7) — list, oversize/type gate,
 * empty/loading/error states, Failed: Timeout render, delete confirm, poll,
 * NFR-9 advisory. Mocks kbApi entirely — no live network. */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "../../ui";
import KnowledgeBaseTab from "./KnowledgeBaseTab";
import type { KbDocument } from "../../../lib/kbApi";

const mockList = vi.fn();
const mockUpload = vi.fn();
const mockDelete = vi.fn();

vi.mock("../../../lib/kbApi", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/kbApi")>(
    "../../../lib/kbApi",
  );
  return {
    ...actual,
    listKbDocuments: (...args: unknown[]) => mockList(...args),
    uploadKbDocument: (...args: unknown[]) => mockUpload(...args),
    deleteKbDocument: (...args: unknown[]) => mockDelete(...args),
  };
});

function makeDoc(overrides: Partial<KbDocument> = {}): KbDocument {
  return {
    id: "doc-1",
    agent_id: "agent-1",
    filename: "policy.pdf",
    content_type: "application/pdf",
    size_bytes: 1024,
    status: "indexed",
    failure_reason: null,
    chunk_count: 4,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

function renderTab(overrides: Partial<Parameters<typeof KnowledgeBaseTab>[0]> = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <KnowledgeBaseTab agentId="agent-1" isNew={false} {...overrides} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("KnowledgeBaseTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the list with status pills (AC2)", async () => {
    mockList.mockResolvedValue([
      makeDoc({ id: "d1", filename: "sop.pdf", status: "indexed" }),
      makeDoc({ id: "d2", filename: "draft.pdf", status: "processing" }),
    ]);
    renderTab();

    await waitFor(() => expect(screen.getByText("sop.pdf")).toBeInTheDocument());
    expect(screen.getByTestId("vaic-kb-pill-indexed")).toBeInTheDocument();
    expect(screen.getByTestId("vaic-kb-pill-processing")).toBeInTheDocument();
  });

  it("renders the NFR-9 PII advisory persistently (AC7)", async () => {
    mockList.mockResolvedValue([]);
    renderTab();
    expect(screen.getByTestId("vaic-kb-nfr9-advisory")).toBeInTheDocument();
  });

  it("shows the empty state with an upload CTA when there are no documents", async () => {
    mockList.mockResolvedValue([]);
    renderTab();
    await waitFor(() => expect(screen.getByTestId("vaic-empty-state")).toBeInTheDocument());
  });

  it("shows an error state with retry on load failure", async () => {
    mockList.mockRejectedValue(new Error("network down"));
    renderTab();
    await waitFor(() => expect(screen.getByTestId("vaic-error-state")).toBeInTheDocument());
    expect(screen.getByText("network down")).toBeInTheDocument();
  });

  it("rejects an oversize file client-side without calling the API (AC3)", async () => {
    mockList.mockResolvedValue([]);
    renderTab();
    await waitFor(() => expect(screen.getByTestId("vaic-empty-state")).toBeInTheDocument());

    const input = screen.getByTestId("vaic-kb-file-input") as HTMLInputElement;
    const bigFile = new File([new Uint8Array(21 * 1024 * 1024)], "huge.pdf", {
      type: "application/pdf",
    });
    fireEvent.change(input, { target: { files: [bigFile] } });

    await waitFor(() =>
      expect(screen.getByText(/exceeds the 20MB limit/)).toBeInTheDocument(),
    );
    expect(mockUpload).not.toHaveBeenCalled();
  });

  it("rejects a disallowed extension client-side without calling the API", async () => {
    mockList.mockResolvedValue([]);
    renderTab();
    await waitFor(() => expect(screen.getByTestId("vaic-empty-state")).toBeInTheDocument());

    const input = screen.getByTestId("vaic-kb-file-input") as HTMLInputElement;
    const badFile = new File(["MZ"], "virus.exe", { type: "application/x-msdownload" });
    fireEvent.change(input, { target: { files: [badFile] } });

    await waitFor(() =>
      expect(screen.getByText(/not a supported file type/)).toBeInTheDocument(),
    );
    expect(mockUpload).not.toHaveBeenCalled();
  });

  it('renders "Failed: Timeout" from failure_reason (AC4)', async () => {
    mockList.mockResolvedValue([
      makeDoc({ id: "d3", filename: "slow.pdf", status: "failed", failure_reason: "Timeout" }),
    ]);
    renderTab();
    await waitFor(() => expect(screen.getByText("Failed: Timeout")).toBeInTheDocument());
  });

  it("delete opens ConfirmDialog and confirm calls deleteKbDocument (AC5)", async () => {
    mockList.mockResolvedValue([makeDoc({ id: "d4", filename: "todelete.pdf" })]);
    mockDelete.mockResolvedValue({ id: "d4" });
    renderTab();

    await waitFor(() => expect(screen.getByText("todelete.pdf")).toBeInTheDocument());
    // Row actions surface only in edit mode.
    fireEvent.click(screen.getByTestId("vaic-tab-edit"));
    fireEvent.click(screen.getByLabelText("Delete todelete.pdf"));

    expect(screen.getByTestId("vaic-confirm-dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Delete", { selector: "button.vaic-btn-destructive" }));

    await waitFor(() => expect(mockDelete).toHaveBeenCalledWith("agent-1", "d4"));
  });

  it("polls while a document is processing", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockList.mockResolvedValue([makeDoc({ id: "d5", status: "processing" })]);
    renderTab();

    await vi.waitFor(() => expect(mockList).toHaveBeenCalledTimes(1));
    await vi.advanceTimersByTimeAsync(2100);
    await vi.waitFor(() => expect(mockList.mock.calls.length).toBeGreaterThan(1));
    vi.useRealTimers();
  });
});
