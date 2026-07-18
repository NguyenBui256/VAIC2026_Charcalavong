import { apiFetch } from "../../lib/api";
import type { AuditEvaluation, AuditEvent, AuditGraph, AuditPayload, AuditSession, AuditSpan, EvaluationCriterion, EvaluationJob } from "./types";

export const auditApi = {
  sessions: (query = "") => apiFetch<AuditSession[]>(`/audit/sessions${query ? `?${query}` : ""}`),
  session: (id: string) => apiFetch<AuditSession>(`/audit/sessions/${id}`),
  spans: (id: string) => apiFetch<AuditSpan[]>(`/audit/sessions/${id}/spans`),
  events: (id: string, after = 0) => apiFetch<AuditEvent[]>(`/audit/sessions/${id}/events?after=${after}&limit=1000`),
  graph: (id: string) => apiFetch<AuditGraph>(`/audit/sessions/${id}/graph`),
  payload: (id: string) => apiFetch<AuditPayload>(`/audit/payloads/${id}`),
  export: (id: string) => apiFetch<Record<string, unknown>>(`/audit/sessions/${id}/export`),
  criteria: () => apiFetch<EvaluationCriterion[]>("/audit/evaluation-criteria"),
  createCriterion: (body: { name: string; description: string }) => apiFetch<EvaluationCriterion>("/audit/evaluation-criteria", { method: "POST", body: JSON.stringify(body) }),
  updateCriterion: (id: string, body: { name: string; description: string }) => apiFetch<EvaluationCriterion>(`/audit/evaluation-criteria/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  archiveCriterion: (id: string) => apiFetch<{ id: string; archived: boolean }>(`/audit/evaluation-criteria/${id}`, { method: "DELETE" }),
  runEvaluation: (sessionId: string, criterionIds: string[]) => apiFetch<EvaluationJob>(`/audit/sessions/${sessionId}/evaluations`, { method: "POST", body: JSON.stringify({ criterion_ids: criterionIds }) }),
  evaluationJob: (id: string) => apiFetch<EvaluationJob>(`/audit/evaluation-jobs/${id}`),
  latestEvaluation: (sessionId: string) => apiFetch<AuditEvaluation | null>(`/audit/sessions/${sessionId}/evaluations/latest`),
};
