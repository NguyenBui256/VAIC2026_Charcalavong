import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import EvaluationTab from "./EvaluationTab";
import type { AuditSession } from "./types";

vi.mock("../../lib/auth", () => ({
  getStoredUser: vi.fn(() => ({ id: "manager-1", role: "manager" })),
}));

const session = {
  status: "completed",
  latest_evaluation: {
    id: "evaluation-1",
    evaluator_name: "LLM Audit Judge",
    evaluator_version: "1",
    evaluator_type: "llm_judge",
    status: "completed",
    score: "0.5",
    metrics: {},
    requested_by_user_id: "manager-1",
    provider: "openai",
    model: "DeepSeek-V4-Flash",
    overall_pass: false,
    summary: "The trace requires remediation before approval.",
    assessment: "One selected quality criterion did not pass.",
    insights: [{ title: "Stable execution", severity: "low", description: "All spans terminated." }],
    issues: [{ severity: "high", category: "output", description: "Final output is missing.", recommendation: "Persist the final response." }],
    strengths: ["All tools completed successfully."],
    criteria: [
      { criterion_id: "criterion-1", name: "Tool usage", description: "", passed: true, confidence: 0.9, rationale: "Tools completed.", evidence: [] },
      { criterion_id: "criterion-2", name: "Complete output", description: "", passed: false, confidence: 0.8, rationale: "Output is unavailable.", evidence: [{ event_sequence: 20 }] },
    ],
    evidence_span_ids: [],
    input_tokens: 100,
    output_tokens: 50,
    latency_ms: 62000,
    created_at: "2026-07-18T10:00:00Z",
  },
} as unknown as AuditSession;

it("renders a structured quality report and filters failed criteria", async () => {
  render(<EvaluationTab session={session} onEvaluate={vi.fn()} onEvidence={vi.fn()} />);

  expect(screen.getByText("Session quality report")).toBeInTheDocument();
  expect(screen.getByText("50")).toBeInTheDocument();
  expect(screen.getByText("Tool usage")).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Failed 1" }));

  expect(screen.queryByText("Tool usage")).not.toBeInTheDocument();
  expect(screen.getByText("Complete output")).toBeInTheDocument();
});
