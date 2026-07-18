/* Story 1.10 — TanStack Query hook for dashboard data (mock).
 *
 * Returns loading / error / data states so the dashboard can render the
 * UX-DR23 loading skeleton and ErrorState. Real wiring (Epic 3/5/6) replaces
 * the `queryFn` only — the hook's signature stays the same.
 *
 * Determinism:
 *  - The mock queryFn returns the same payload every run.
 *  - For tests that want to exercise loading/error paths, a module-level
 *    `__setDashboardMockMode` mutator switches the queryFn between:
 *      "populated" (default), "empty", "error".
 *  - An artificial delay simulates network latency so the loading skeleton is
 *    visible in dev. The delay is disabled in test env (vitest) by default.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import {
  mockDashboardPopulated,
  mockDashboardEmpty,
  mockDashboardErrorFactory,
  type DashboardData,
} from "../lib/mockData";
import { auditApi } from "../features/audit/api";
import type { AuditStatus } from "../features/audit/types";
import type { RunState } from "../lib/icons";

export type DashboardMockMode = "populated" | "empty" | "error";

let mockMode: DashboardMockMode = "populated";
let artificialDelayMs = 600;

/** Test hook: switch the mock between populated / empty / error. */
export function __setDashboardMockMode(mode: DashboardMockMode): void {
  mockMode = mode;
}

/** Test hook: set the artificial delay (0 to disable). */
export function __setDashboardMockDelay(ms: number): void {
  artificialDelayMs = ms;
}

/** Test hook: reset to defaults. */
export function __resetDashboardMock(): void {
  mockMode = "populated";
  artificialDelayMs = 600;
}

async function fetchDashboard(): Promise<DashboardData> {
  if (artificialDelayMs > 0) {
    await new Promise((r) => setTimeout(r, artificialDelayMs));
  }
  if (import.meta.env.MODE === "test") {
    if (mockMode === "empty") return mockDashboardEmpty;
    if (mockMode === "error") mockDashboardErrorFactory()();
    return mockDashboardPopulated;
  }
  const sessions = await auditApi.sessions("limit=20");
  const stateMapping: Record<AuditStatus, RunState> = {
    pending: "pending", running: "running", awaiting_human: "escalated",
    completed: "success", failed: "error", timed_out: "error",
    cancelled: "error", skipped: "draft",
  };
  const state = (value: AuditStatus): RunState => stateMapping[value];
  return {
    kpis: {
      activeRuns: sessions.filter((item) => item.status === "running").length,
      pendingEscalations: sessions.filter((item) => item.status === "awaiting_human").length,
      todayMiniAppEvents: sessions.filter((item) => item.trigger_type === "app_event").length,
    },
    escalations: sessions.filter((item) => item.status === "awaiting_human").map((item) => ({
      id: `escalation-${item.id}`, runId: item.id, runName: item.name,
      reason: item.failure_summary || "Human decision required",
      createdAtOffsetMs: new Date(item.started_at ?? item.created_at).getTime() - Date.now(),
    })),
    recentRuns: sessions.slice(0, 5).map((item) => ({
      id: item.id, name: item.name || "Workflow run", state: state(item.status),
      durationMs: item.started_at && item.ended_at ? new Date(item.ended_at).getTime() - new Date(item.started_at).getTime() : 0,
      startedAtOffsetMs: new Date(item.started_at ?? item.created_at).getTime() - Date.now(),
    })),
  };
}

export interface UseDashboardDataResult {
  query: UseQueryResult<DashboardData, Error>;
  /** Convenience flags for the three states the dashboard cares about. */
  isLoading: boolean;
  isError: boolean;
  data: DashboardData | undefined;
}

export function useDashboardData(): UseDashboardDataResult {
  const query = useQuery<DashboardData, Error>({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard,
  });

  return {
    query,
    isLoading: query.isLoading,
    isError: query.isError,
    data: query.data,
  };
}

/** Expose the queryKey for tests that need to invalidate / refetch. */
export const DASHBOARD_QUERY_KEY = ["dashboard"] as const;
