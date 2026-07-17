/* Epic 6 (FR-22) — Trace Dashboard / Audit Trail API layer.
 *
 * Typed wrapper around apiFetch for the read-only audit endpoint
 * (backend: app/modules/audit/routes.py). The entry shape is frozen against
 * core/ports/audit.py (AuditEntry). This surface only READS the trail — it is
 * independent of the Orchestrator (Epic 3); it renders whatever audit rows
 * exist for the tenant.
 */

import { apiFetch } from "./api";

/** One append-only audit_trail row (PRD FR-21 / AuditEntry). */
export interface AuditEntry {
  id: string;
  run_id: string | null;
  step_id: string | null;
  agent_id: string | null;
  ts: string | null;
  /** e.g. "decomposition", "task_dispatch", "tool_call", "model_invocation",
   * "aggregation", "escalation", "mini_app_emission", "workflow_run.transition". */
  type: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  latency_ms: number;
  model: string;
}

export interface AuditListParams {
  /** Scope to a single Run's timeline (ordered oldest→newest). */
  run_id?: string;
  /** Filter by entry type. */
  type?: string;
  /** Max rows (backend caps at 500). */
  limit?: number;
}

function buildQuery(params: Record<string, string | undefined>): string {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) usp.set(key, value);
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export function listAuditEntries(params: AuditListParams = {}): Promise<AuditEntry[]> {
  const qs = buildQuery({
    run_id: params.run_id,
    type: params.type,
    limit: params.limit ? String(params.limit) : undefined,
  });
  return apiFetch<AuditEntry[]>(`/audit${qs}`);
}
