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
  if (mockMode === "empty") return mockDashboardEmpty;
  if (mockMode === "error") mockDashboardErrorFactory()();
  return mockDashboardPopulated;
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
