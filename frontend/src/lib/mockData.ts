/* Story 1.10 — Deterministic mock data for Dashboard surface.
 *
 * Real wiring comes in Epics 3, 5, 6. Until then we serve mock data via
 * TanStack Query so the UI is fully testable and demoable.
 *
 * Determinism rules:
 *  - No Math.random() — use a seeded PRNG (mulberry32) so test snapshots are stable.
 *  - Timestamps are relative to a fixed anchor (MOCK_NOW) so they don't drift
 *    across runs, but still look "recent" in human terms.
 *  - All IDs are derived from the seed, not from Date.now() / crypto.
 */

import type { RunState } from "./icons";

/* ──────────────────────────────────────────────────────────────────────────
 * Seeded PRNG — mulberry32. Deterministic given the same seed.
 * ──────────────────────────────────────────────────────────────────────── */

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Pick a deterministic element from an array using a PRNG draw. */
function pick<T>(rand: () => number, arr: readonly T[]): T {
  return arr[Math.floor(rand() * arr.length) % arr.length];
}

/* ──────────────────────────────────────────────────────────────────────────
 * Fixed anchor time — tests must not depend on wall-clock.
 * Real "today" feel is achieved by expressing timestamps as deltas from this
 * anchor; the dashboard formats them as relative ("14s ago", "2m ago").
 * ──────────────────────────────────────────────────────────────────────── */

/** Anchor used for all mock timestamps. 2026-07-17T09:30:00Z (deterministic). */
export const MOCK_NOW = new Date("2026-07-17T09:30:00Z").getTime();

/* ──────────────────────────────────────────────────────────────────────────
 * Domain types — these mirror the shapes Epic 3/5/6 will eventually serve.
 * Kept narrow to the dashboard's needs; full Run / Escalation schemas come later.
 * ──────────────────────────────────────────────────────────────────────── */

export interface KpiCounts {
  activeRuns: number;
  pendingEscalations: number;
  todayMiniAppEvents: number;
}

export interface EscalationItem {
  id: string;
  runId: string;
  runName: string;
  reason: string;
  /** Millis since MOCK_NOW (negative = past). */
  createdAtOffsetMs: number;
}

export interface RunSummary {
  id: string;
  name: string;
  state: RunState;
  /** Duration in milliseconds (0 for pending/running). */
  durationMs: number;
  /** Millis since MOCK_NOW (negative = past). */
  startedAtOffsetMs: number;
}

export interface DashboardData {
  kpis: KpiCounts;
  escalations: EscalationItem[];
  recentRuns: RunSummary[];
}

/* ──────────────────────────────────────────────────────────────────────────
 * Deterministic mock datasets.
 *
 * Three suites are exported:
 *  - mockDashboardPopulated: the "happy path" with non-zero KPIs and items.
 *  - mockDashboardEmpty: all zeros + empty arrays (for UX-DR23 empty states).
 *  - mockDashboardErrorFactory: returns a thunk that throws (for error states).
 * ──────────────────────────────────────────────────────────────────────── */

const ESCALATION_REASONS = [
  "Compliance vs Credit conflict",
  "Missing KYC document",
  "Operations flagged for review",
  "AML threshold exceeded",
  "Manual override requested",
] as const;

const RUN_NAMES = [
  "Business Loan Pre-Screen",
  "AML Sweep Q3",
  "KYC Refresh Batch",
  "Loan #LOAN-204 Underwriting",
  "Daily Risk Digest",
  "Onboarding Check #OB-512",
] as const;

const RUN_STATES_FOR_RECENT: RunState[] = [
  "running",
  "success",
  "success",
  "error",
  "escalated",
];

/**
 * Populated dashboard — represents a normal day with active work.
 * KPIs and lists are pre-computed (not derived from a seed) so values are
 * obvious in tests and the storybook of dashboard states.
 */
export const mockDashboardPopulated: DashboardData = {
  kpis: {
    activeRuns: 2,
    pendingEscalations: 1,
    todayMiniAppEvents: 14,
  },
  escalations: [
    {
      id: "esc-001",
      runId: "run-LOAN-204",
      runName: "Business Loan #LOAN-204",
      reason: ESCALATION_REASONS[0],
      createdAtOffsetMs: -1000 * 60 * 4, // 4 min ago
    },
  ],
  recentRuns: [
    {
      id: "run-001",
      name: RUN_NAMES[0],
      state: "running",
      durationMs: 14_000,
      startedAtOffsetMs: -14_000,
    },
    {
      id: "run-002",
      name: "Business Loan #LOAN-203",
      state: "success",
      durationMs: 22_000,
      startedAtOffsetMs: -1000 * 60 * 2,
    },
    {
      id: "run-003",
      name: RUN_NAMES[1],
      state: "success",
      durationMs: 64_000,
      startedAtOffsetMs: -1000 * 60 * 8,
    },
    {
      id: "run-004",
      name: "Loan Pre-Screen #LOAN-201",
      state: "error",
      durationMs: 38_000,
      startedAtOffsetMs: -1000 * 60 * 15,
    },
    {
      id: "run-005",
      name: RUN_NAMES[2],
      state: "escalated",
      durationMs: 90_000,
      startedAtOffsetMs: -1000 * 60 * 22,
    },
  ],
};

/**
 * Empty dashboard — all KPIs zero, all lists empty.
 * Used to exercise UX-DR23 empty states.
 */
export const mockDashboardEmpty: DashboardData = {
  kpis: {
    activeRuns: 0,
    pendingEscalations: 0,
    todayMiniAppEvents: 0,
  },
  escalations: [],
  recentRuns: [],
};

/**
 * Error factory — returns a function that throws a deterministic Error.
 * The hook calls this inside `queryFn` to simulate a failed fetch.
 */
export function mockDashboardErrorFactory(): () => never {
  const err = new Error("Failed to load dashboard (mock)");
  return () => {
    throw err;
  };
}

/* ──────────────────────────────────────────────────────────────────────────
 * Seeded "fuzzy" generator — for stress / property-style tests that need
 * variable but deterministic data. Not used by the default hook.
 * ──────────────────────────────────────────────────────────────────────── */

export interface SeededDashboardOptions {
  seed?: number;
  escalationCount?: number;
  recentRunCount?: number;
}

export function generateSeededDashboard(
  opts: SeededDashboardOptions = {},
): DashboardData {
  const {
    seed = 0xc0ffee,
    escalationCount = 3,
    recentRunCount = 5,
  } = opts;
  const rand = mulberry32(seed);

  const escalations: EscalationItem[] = Array.from({
    length: escalationCount,
  }).map((_, i) => ({
    id: `esc-seeded-${String(i).padStart(3, "0")}`,
    runId: `run-seeded-${String(i).padStart(3, "0")}`,
    runName: pick(rand, RUN_NAMES),
    reason: pick(rand, ESCALATION_REASONS),
    createdAtOffsetMs: -1000 * 60 * (i + 1) * 3,
  }));

  const recentRuns: RunSummary[] = Array.from({
    length: recentRunCount,
  }).map((_, i) => {
    const state = RUN_STATES_FOR_RECENT[i % RUN_STATES_FOR_RECENT.length];
    return {
      id: `run-seeded-${String(i).padStart(3, "0")}`,
      name: pick(rand, RUN_NAMES),
      state,
      durationMs:
        state === "pending" || state === "running" ? 0 : 10_000 + i * 7_000,
      startedAtOffsetMs: -1000 * 60 * (i + 1) * 5,
    };
  });

  return {
    kpis: {
      activeRuns: recentRuns.filter((r) => r.state === "running").length,
      pendingEscalations: escalationCount,
      todayMiniAppEvents: Math.floor(rand() * 50),
    },
    escalations,
    recentRuns,
  };
}

/* ──────────────────────────────────────────────────────────────────────────
 * Formatting helpers — relative time and duration in a stable, locale-free
 * form so tests can assert exact strings.
 * ──────────────────────────────────────────────────────────────────────── */

/** Format a duration in ms as e.g. "14s", "1m 04s", "2m". */
export function formatDuration(ms: number): string {
  if (ms <= 0) return "0s";
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  if (m === 0) return `${s}s`;
  if (s === 0) return `${m}m`;
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

/** Format a relative timestamp as e.g. "just now", "4m ago", "2h ago". */
export function formatRelativeFromOffset(
  offsetMs: number,
  nowMs: number = MOCK_NOW,
): string {
  const delta = nowMs + offsetMs - nowMs; // = offsetMs (kept explicit for clarity)
  const abs = Math.abs(delta);
  const sec = Math.floor(abs / 1000);
  if (sec < 60) return "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  return `${day}d ago`;
}
