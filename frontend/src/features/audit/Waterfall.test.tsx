import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import Waterfall from "./Waterfall";
import type { AuditSpan } from "./types";

const span: AuditSpan = {
  id: "span-1", session_id: "session-1", parent_span_id: null,
  logical_node_id: "credit", task_id: null, agent_id: "agent-1", department_id: "dept-1",
  actor_type: "agent", node_type: "llm", name: "Credit synthesis", attempt_no: 1,
  status: "completed", started_at: "2026-07-18T08:00:00Z", ended_at: "2026-07-18T08:00:01Z",
  duration_ms: 1000, ttft_ms: 120, provider: "anthropic", model: "claude",
  tool_name: "", tool_version: "", kb_id: null, kb_version: "", error_code: "", error_message: "",
  input_tokens: 100, output_tokens: 25, cached_tokens: 0, reasoning_tokens: 0,
  estimated_cost_usd: "0.001", input_payload_id: null, output_payload_id: null, attributes: {},
};

it("renders duration and selects an execution span", () => {
  const onSelect = vi.fn();
  render(<Waterfall spans={[span]} onSelect={onSelect} />);
  expect(screen.getByText("Credit synthesis")).toBeInTheDocument();
  expect(screen.getByText("1000 ms")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("listitem"));
  expect(onSelect).toHaveBeenCalledWith(span);
});

it("renders an explicit empty state", () => {
  render(<Waterfall spans={[]} onSelect={vi.fn()} />);
  expect(screen.getByText("No execution spans recorded.")).toBeInTheDocument();
});
