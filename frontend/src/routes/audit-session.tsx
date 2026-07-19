import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowLeft, CheckCircle2, Copy, Download, Radio, ShieldAlert } from "lucide-react";
import { auditApi } from "../features/audit/api";
import AuditInspector from "../features/audit/AuditInspector";
import AuditStatusPill from "../features/audit/AuditStatus";
import EvaluationDrawer from "../features/audit/EvaluationDrawer";
import EvaluationTab from "../features/audit/EvaluationTab";
import TraceGraph from "../features/audit/TraceGraph";
import Waterfall from "../features/audit/Waterfall";
import { useAuditStream } from "../features/audit/useAuditStream";
import type { AuditEvent, AuditSpan } from "../features/audit/types";
import { ErrorState, Skeleton } from "../components/ui";

const tabs = ["overview", "graph", "waterfall", "evaluation", "raw"] as const;
type Tab = typeof tabs[number];

export default function AuditSessionPage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const activeTab = (tabs.includes(params.get("view") as Tab) ? params.get("view") : "overview") as Tab;
  const sessionQuery = useQuery({ queryKey: ["audit-session", sessionId], queryFn: () => auditApi.session(sessionId) });
  const spansQuery = useQuery({ queryKey: ["audit-spans", sessionId], queryFn: () => auditApi.spans(sessionId) });
  const eventsQuery = useQuery({ queryKey: ["audit-events", sessionId], queryFn: () => auditApi.events(sessionId) });
  const graphQuery = useQuery({ queryKey: ["audit-graph", sessionId], queryFn: () => auditApi.graph(sessionId) });
  const [selected, setSelected] = useState<AuditSpan | null>(null);
  const [evaluationOpen, setEvaluationOpen] = useState(false);
  const session = sessionQuery.data;
  const spans = spansQuery.data ?? [];
  const events = eventsQuery.data ?? [];
  const streamState = useAuditStream(sessionId, session?.status === "running" || session?.status === "awaiting_human", session?.last_sequence ?? 0);

  const selectSpan = (span: AuditSpan) => {
    setSelected(span);
    const next = new URLSearchParams(params); next.set("span", span.id); setParams(next, { replace: true });
  };
  const setTab = (tab: Tab) => { const next = new URLSearchParams(params); next.set("view", tab); setParams(next); };

  if (sessionQuery.isLoading) return <main className="audit-page"><Skeleton height="220px" /><Skeleton height="400px" /></main>;
  if (sessionQuery.isError || !session) return <main className="audit-page"><ErrorState message="Audit session not found or outside your access scope." /></main>;

  const exportAudit = async () => {
    const result = await auditApi.export(sessionId);
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
    anchor.href = url; anchor.download = `audit-${session.run_id}.json`; anchor.click(); URL.revokeObjectURL(url);
  };

  const onEvidence = (evidence: { span_id?: string; event_sequence?: number }) => {
    if (evidence.span_id) { const span = spans.find((item) => item.id === evidence.span_id); if (span) selectSpan(span); }
    if (evidence.event_sequence) { const next = new URLSearchParams(params); next.set("view", "raw"); next.set("sequence", String(evidence.event_sequence)); setParams(next); }
  };

  return <main className="audit-page audit-session-page">
    <header className="audit-session-header">
      <button className="audit-icon-button" onClick={() => navigate("/audit")} aria-label="Back to audit explorer"><ArrowLeft /></button>
      <div className="audit-session-title"><span className="audit-eyebrow">Trace session · {session.run_id.slice(0, 16)}</span>
        <h1>{session.name || "Workflow run"}</h1><div className="audit-title-meta"><AuditStatusPill status={session.status} />
          <span>{session.trigger_type.replaceAll("_", " ")}</span><span>workflow v{session.workflow_version || "snapshot"}</span>
          {(session.status === "running" || session.status === "awaiting_human") && <span className="audit-live-badge"><Radio size={14} />{streamState}</span>}
        </div></div>
      <div className="audit-header-actions"><button className="vaic-btn vaic-btn-secondary" onClick={() => navigator.clipboard.writeText(location.href)}><Copy size={16} /> Share</button>
        <button className="vaic-btn vaic-btn-primary" onClick={() => void exportAudit()}><Download size={16} /> Export audit</button></div>
    </header>

    {!session.integrity?.valid && <div className="audit-integrity-alert"><ShieldAlert /><div><strong>Trace integrity requires attention</strong><p>{session.integrity?.problems.join(" · ")}</p></div></div>}
    <Kpis session={session} />
    <nav className="audit-tabs" aria-label="Trace views">{tabs.map((tab) => <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => setTab(tab)}>{tab}</button>)}</nav>
    <div className="audit-trace-layout">
      <section className={`audit-panel audit-trace-content ${activeTab === "evaluation" ? "audit-evaluation-content" : ""}`}>
        {activeTab === "overview" && <Overview session={session} spans={spans} />}
        {activeTab === "graph" && (graphQuery.data ? <TraceGraph graph={graphQuery.data} onSelect={selectSpan} /> : <Skeleton height="600px" />)}
        {activeTab === "waterfall" && <Waterfall spans={spans} onSelect={selectSpan} />}
        {activeTab === "evaluation" && <EvaluationTab session={session} onEvaluate={() => setEvaluationOpen(true)} onEvidence={onEvidence} />}
        {activeTab === "raw" && <RawEvents events={events} integrity={session.integrity} />}
      </section>
      <AuditInspector span={selected} onClose={() => setSelected(null)} />
    </div>
    <div className="sr-only" aria-live="polite">{events.length} audit events loaded.</div>
    <EvaluationDrawer sessionId={sessionId} open={evaluationOpen} terminal={["completed", "failed", "timed_out", "cancelled"].includes(session.status)} onClose={() => setEvaluationOpen(false)} />
  </main>;
}

function Kpis({ session }: { session: NonNullable<ReturnType<typeof useQuery>["data"]> & Record<string, any> }) {
  const duration = session.ended_at && session.started_at ? new Date(session.ended_at).getTime() - new Date(session.started_at).getTime() : Date.now() - new Date(session.started_at ?? session.created_at).getTime();
  const values = [
    ["Duration", `${Math.max(0, duration / 1000).toFixed(1)}s`], ["Critical path", `${session.critical_path_ms}ms`],
    ["Total tokens", (session.input_tokens + session.output_tokens).toLocaleString()], ["Estimated cost", `$${Number(session.estimated_cost_usd).toFixed(5)}`],
    ["LLM / Tools / RAG", `${session.llm_call_count} / ${session.tool_call_count} / ${session.rag_call_count}`],
    ["Retries / Escalations", `${session.retry_count} / ${session.escalation_count}`],
  ];
  return <section className="audit-kpis">{values.map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</section>;
}

function Overview({ session, spans }: { session: any; spans: AuditSpan[] }) {
  const slowest = [...spans].filter((span) => span.duration_ms != null).sort((a, b) => (b.duration_ms ?? 0) - (a.duration_ms ?? 0))[0];
  return <div className="audit-overview-grid">
    <article><span className="audit-eyebrow">Execution summary</span><h2>{spans.length} runtime nodes across {session.agent_count} agents</h2>
      <p>Started by {session.trigger_type}; correlation chain <code>{session.correlation_id}</code>.</p>
      {slowest && <p>Slowest observed node: <strong>{slowest.name}</strong> at {slowest.duration_ms} ms.</p>}</article>
    <article><span className="audit-eyebrow">Integrity</span><h2>{session.integrity?.valid ? "Evidence chain verified" : "Verification failed"}</h2>
      <p>{session.last_sequence} immutable events · {session.redaction_count} sensitive values redacted.</p>
      {session.integrity?.valid && <CheckCircle2 className="audit-good" />}</article>
    <article><span className="audit-eyebrow">Result</span><h2>{session.status === "completed" ? "Workflow completed" : session.status.replaceAll("_", " ")}</h2>
      <p>{session.failure_summary || "Open the execution graph or a span to inspect the evidence and output payload."}</p></article>
  </div>;
}

function RawEvents({ events, integrity }: { events: AuditEvent[]; integrity: any }) {
  const parent = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({ count: events.length, getScrollElement: () => parent.current, estimateSize: () => 76, overscan: 8 });
  return <div><div className={integrity?.valid ? "audit-integrity-ok" : "audit-integrity-alert"}>{integrity?.valid ? <CheckCircle2 /> : <ShieldAlert />}<strong>{integrity?.valid ? "Hash chain and sequence verified" : "Integrity validation failed"}</strong></div>
    <div ref={parent} className="audit-raw-list"><div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>{virtualizer.getVirtualItems().map((item) => { const event = events[item.index]; return <div key={event.id} className="audit-event-row" style={{ transform: `translateY(${item.start}px)`, height: item.size }}>
      <span>#{event.sequence_no}</span><strong>{event.event_type}</strong><span>{new Date(event.occurred_at).toLocaleTimeString()}</span><code>{event.event_hash.slice(0, 16)}…</code>
    </div>; })}</div></div></div>;
}
