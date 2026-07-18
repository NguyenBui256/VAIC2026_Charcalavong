import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import CodeBlock from "../../components/ui/CodeBlock";
import { auditApi } from "./api";
import type { AuditSpan } from "./types";
import AuditStatusPill from "./AuditStatus";

function Payload({ id, label }: { id: string | null; label: string }) {
  const query = useQuery({ queryKey: ["audit-payload", id], queryFn: () => auditApi.payload(id!), enabled: Boolean(id) });
  if (!id) return null;
  if (query.isLoading) return <p className="audit-muted">Loading {label.toLowerCase()}…</p>;
  if (query.isError) return <p className="audit-warning">{label} is redacted or outside your access scope.</p>;
  return <CodeBlock label={`${label} · ${query.data?.classification}`} code={JSON.stringify(query.data?.data, null, 2)} />;
}

export default function AuditInspector({ span, onClose }: { span: AuditSpan | null; onClose: () => void }) {
  if (!span) return null;
  return (
    <aside className="audit-inspector" aria-label="Span inspector">
      <header><div><span className="audit-eyebrow">{span.node_type} span</span><h2>{span.name}</h2></div>
        <button className="audit-icon-button" onClick={onClose} aria-label="Close inspector"><X size={18} /></button></header>
      <div className="audit-inspector-summary">
        <AuditStatusPill status={span.status} />
        <dl>
          <dt>Duration</dt><dd>{span.duration_ms == null ? "Running" : `${span.duration_ms} ms`}</dd>
          <dt>Attempt</dt><dd>{span.attempt_no}</dd>
          <dt>Agent</dt><dd>{span.agent_id ?? "Orchestrator / system"}</dd>
          {span.model && <><dt>Model</dt><dd>{span.provider} / {span.model}</dd></>}
          {span.tool_name && <><dt>Tool</dt><dd>{span.tool_name} {span.tool_version}</dd></>}
          <dt>Tokens</dt><dd>{span.input_tokens.toLocaleString()} in · {span.output_tokens.toLocaleString()} out</dd>
          <dt>Cost</dt><dd>${Number(span.estimated_cost_usd).toFixed(6)}</dd>
        </dl>
      </div>
      {span.error_message && <div className="audit-error-box"><strong>{span.error_code || "Execution error"}</strong><p>{span.error_message}</p></div>}
      <Payload id={span.input_payload_id} label="Input" />
      <Payload id={span.output_payload_id} label="Output" />
      <CodeBlock label="Span metadata" code={JSON.stringify({ id: span.id, parent_span_id: span.parent_span_id, task_id: span.task_id, ...span.attributes }, null, 2)} />
    </aside>
  );
}
