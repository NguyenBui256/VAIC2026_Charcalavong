export type AuditStatus =
  | "pending" | "running" | "awaiting_human" | "completed"
  | "failed" | "timed_out" | "cancelled" | "skipped";

export interface AuditSession {
  id: string;
  run_id: string;
  department_id: string | null;
  workflow_id: string | null;
  workflow_version: string;
  correlation_id: string;
  parent_session_id: string | null;
  trace_id: string;
  name: string;
  trigger_type: string;
  initiator_user_id: string | null;
  status: AuditStatus;
  current_span_id: string | null;
  input_payload_id: string | null;
  result_payload_id: string | null;
  failure_summary: string;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  llm_call_count: number;
  tool_call_count: number;
  rag_call_count: number;
  agent_count: number;
  retry_count: number;
  escalation_count: number;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  reasoning_tokens: number;
  estimated_cost_usd: string;
  human_wait_ms: number;
  critical_path_ms: number;
  last_sequence: number;
  last_hash: string;
  completeness_status: string;
  redaction_count: number;
  attributes: Record<string, unknown>;
  integrity?: AuditIntegrity;
  evaluations?: AuditEvaluation[];
  latest_evaluation?: AuditEvaluation | null;
}

export interface AuditSpan {
  id: string;
  session_id: string;
  parent_span_id: string | null;
  logical_node_id: string;
  task_id: string | null;
  agent_id: string | null;
  department_id: string | null;
  actor_type: string;
  node_type: string;
  name: string;
  attempt_no: number;
  status: AuditStatus;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  ttft_ms: number | null;
  provider: string;
  model: string;
  tool_name: string;
  tool_version: string;
  kb_id: string | null;
  kb_version: string;
  error_code: string;
  error_message: string;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  reasoning_tokens: number;
  estimated_cost_usd: string;
  input_payload_id: string | null;
  output_payload_id: string | null;
  attributes: Record<string, unknown>;
}

export interface AuditEvent {
  id: string;
  session_id: string;
  span_id: string | null;
  parent_span_id: string | null;
  sequence_no: number;
  occurred_at: string;
  event_type: string;
  phase: string;
  severity: string;
  actor_type: string;
  actor_id: string | null;
  status: AuditStatus | null;
  input_payload_id: string | null;
  output_payload_id: string | null;
  attributes: Record<string, unknown>;
  schema_version: number;
  prev_hash: string;
  event_hash: string;
}

export interface AuditGraph {
  nodes: AuditSpan[];
  edges: { id: string; source: string; target: string; type: string }[];
}

export interface AuditPayload {
  id: string;
  classification: string;
  data: unknown;
  byte_size: number;
  sha256: string;
  redaction_count: number;
  redaction_paths: string[];
}

export interface AuditIntegrity {
  valid: boolean;
  event_count: number;
  last_hash: string;
  problems: string[];
  orphan_span_ids: string[];
}

export interface AuditEvaluation {
  id: string;
  evaluator_name: string;
  evaluator_version: string;
  evaluator_type: string;
  status: string;
  score: string | null;
  metrics: Record<string, unknown>;
  requested_by_user_id: string | null;
  provider: string;
  model: string;
  overall_pass: boolean | null;
  summary: string;
  assessment: string;
  insights: EvaluationInsight[];
  issues: EvaluationIssue[];
  strengths: string[];
  criteria: EvaluationCriterionResult[];
  evidence_span_ids: string[];
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  created_at: string;
}

export interface EvaluationCriterion {
  id: string;
  name: string;
  description: string;
  created_by_user_id: string;
  is_active: boolean;
  can_edit: boolean;
}

export interface EvaluationCriterionResult {
  criterion_id: string;
  name: string;
  description: string;
  passed: boolean;
  confidence: number;
  rationale: string;
  evidence: { span_id?: string; event_sequence?: number; payload_sha256?: string }[];
}

export interface EvaluationInsight { title?: string; severity?: string; description?: string; evidence?: unknown[] }
export interface EvaluationIssue { severity?: string; category?: string; description?: string; impact?: string; recommendation?: string; evidence?: unknown[] }

export interface EvaluationJob {
  id: string;
  session_id: string;
  status: "queued" | "collecting_context" | "judging" | "validating" | "completed" | "failed";
  phase: string;
  progress: number;
  error_code: string;
  error_message: string;
  evaluation_id: string | null;
}
