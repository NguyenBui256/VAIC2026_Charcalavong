import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import AuditExplorerPage from "./audit-explorer";
import { auditApi } from "../features/audit/api";

vi.mock("../features/audit/api", () => ({ auditApi: { sessions: vi.fn() } }));

it("renders trace session summaries from the Audit V2 API", async () => {
  vi.mocked(auditApi.sessions).mockResolvedValue([{
    id: "session-1", run_id: "run-0000000000001", department_id: null, workflow_id: null,
    workflow_version: "2", correlation_id: "correlation", parent_session_id: null,
    trace_id: "trace", name: "Loan pre-screen", trigger_type: "manual",
    initiator_user_id: "user", status: "completed", current_span_id: null,
    input_payload_id: null, result_payload_id: null, failure_summary: "",
    created_at: "2026-07-18T08:00:00Z", started_at: "2026-07-18T08:00:00Z",
    ended_at: "2026-07-18T08:00:03Z", llm_call_count: 2, tool_call_count: 1,
    rag_call_count: 1, agent_count: 3, retry_count: 0, escalation_count: 0,
    input_tokens: 1000, output_tokens: 250, cached_tokens: 0, reasoning_tokens: 0,
    estimated_cost_usd: "0.012", human_wait_ms: 0, critical_path_ms: 2000,
    last_sequence: 20, last_hash: "hash", completeness_status: "complete",
    redaction_count: 2, attributes: {},
  }]);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><AuditExplorerPage /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText("Loan pre-screen")).toBeInTheDocument();
  expect(screen.getByText("1,250")).toBeInTheDocument();
  expect(screen.getByText("complete")).toBeInTheDocument();
});
