/* Sub-project 3C — single source mapping backend run/node statuses onto the
 * app's 6 RunStates (lib/icons stateMapping, reused by StatusPill) + pretty
 * labels. Keeps status→color/label logic in one place (spec §4.4 deliverable).
 */

import type { RunState } from "./icons";

/** Run statuses after which polling stops (no further engine progress). */
export const TERMINAL_RUN_STATUSES = [
  "completed",
  "failed",
  "timed_out",
  "completed_with_failures",
] as const;

export function isTerminalRun(status: string): boolean {
  return (TERMINAL_RUN_STATUSES as readonly string[]).includes(status);
}

/** Map any backend run/node status to one of the 6 visual RunStates. */
export function runStateFor(status: string): RunState {
  switch (status) {
    case "completed":
      return "success";
    case "failed":
    case "timed_out":
    case "rejected":
      return "error";
    case "awaiting_human":
    case "awaiting_approval":
    case "completed_with_failures":
      return "escalated";
    case "running":
      return "running";
    case "rolled_back":
    case "skipped":
      return "draft";
    case "pending":
    default:
      return "pending";
  }
}

/** Human-readable label for a raw status (e.g. "awaiting_approval" → "Awaiting approval"). */
export function statusLabel(status: string): string {
  const words = status.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
