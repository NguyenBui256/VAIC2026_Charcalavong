import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import EvaluationDrawer from "./EvaluationDrawer";
import { auditApi } from "./api";

vi.mock("./api", () => ({
  auditApi: {
    criteria: vi.fn(),
    createCriterion: vi.fn(),
    updateCriterion: vi.fn(),
    archiveCriterion: vi.fn(),
    runEvaluation: vi.fn(),
    evaluationJob: vi.fn(),
  },
}));
vi.mock("../../lib/auth", () => ({
  getStoredUser: vi.fn(() => ({ id: "manager-1", role: "manager" })),
}));

beforeEach(() => {
  vi.mocked(auditApi.criteria).mockResolvedValue([
    {
      id: "criterion-1",
      name: "Evidence grounded",
      description: "Conclusions cite trace evidence.",
      created_by_user_id: "manager-1",
      is_active: true,
      can_edit: true,
    },
  ]);
});

it("loads shared criteria and enables evaluation for a terminal session", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <EvaluationDrawer
        sessionId="session-1"
        open
        terminal
        onClose={vi.fn()}
      />
    </QueryClientProvider>,
  );

  expect(await screen.findByText("Evidence grounded")).toBeInTheDocument();
  expect(screen.getByRole("checkbox")).toBeChecked();
  expect(screen.getByRole("button", { name: "Run evaluation" })).toBeEnabled();
  expect(screen.getByText("Add criterion")).toBeInTheDocument();
});
