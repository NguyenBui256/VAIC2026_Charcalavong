import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Activity, Filter, Search } from "lucide-react";
import Table, { type TableColumn } from "../components/ui/Table";
import { EmptyState, ErrorState, Skeleton } from "../components/ui";
import { auditApi } from "../features/audit/api";
import type { AuditSession } from "../features/audit/types";
import AuditStatusPill from "../features/audit/AuditStatus";

const columns: TableColumn<AuditSession>[] = [
  { key: "name", header: "Session", render: (row) => <div><strong>{row.name || "Workflow run"}</strong><small className="audit-table-sub">{row.run_id.slice(0, 13)}…</small></div> },
  { key: "status", header: "Status", render: (row) => <AuditStatusPill status={row.status} /> },
  { key: "trigger", header: "Trigger", render: (row) => row.trigger_type.replaceAll("_", " ") },
  { key: "started", header: "Started", render: (row) => new Date(row.started_at ?? row.created_at).toLocaleString() },
  { key: "agents", header: "Agents", render: (row) => row.agent_count },
  { key: "tokens", header: "Tokens", render: (row) => (row.input_tokens + row.output_tokens).toLocaleString() },
  { key: "cost", header: "Cost", render: (row) => `$${Number(row.estimated_cost_usd).toFixed(4)}` },
  { key: "integrity", header: "Integrity", render: (row) => <span className={row.completeness_status === "complete" ? "audit-good" : "audit-warning"}>{row.completeness_status}</span> },
];

export default function AuditExplorerPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const queryString = params.toString();
  const query = useQuery({ queryKey: ["audit-sessions", queryString], queryFn: () => auditApi.sessions(queryString) });
  const setFilter = (name: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value); else next.delete(name);
    setParams(next);
  };
  return (
    <main className="audit-page">
      <header className="audit-page-header">
        <div><span className="audit-eyebrow">Trace Session Explorer</span><h1>Audit & Decision Provenance</h1>
          <p>Follow every agent decision, model call, tool invocation and human intervention.</p></div>
        <div className="audit-live-badge"><Activity size={16} /> Append-only evidence</div>
      </header>
      <section className="audit-filterbar" aria-label="Audit filters">
        <Search size={16} />
        <input aria-label="Workflow ID" placeholder="Filter workflow ID" value={params.get("workflow_id") ?? ""} onChange={(event) => setFilter("workflow_id", event.target.value)} />
        <select aria-label="Status" value={params.get("status") ?? ""} onChange={(event) => setFilter("status", event.target.value)}>
          <option value="">All statuses</option><option value="running">Running</option><option value="awaiting_human">Awaiting human</option>
          <option value="completed">Completed</option><option value="failed">Failed</option><option value="timed_out">Timed out</option>
        </select>
        <select aria-label="Trigger" value={params.get("trigger_type") ?? ""} onChange={(event) => setFilter("trigger_type", event.target.value)}>
          <option value="">All triggers</option><option value="manual">Manual</option><option value="schedule">Schedule</option>
          <option value="app_event">App event</option><option value="follow_up">Follow-up</option>
        </select><Filter size={16} />
      </section>
      <section className="audit-panel">
        {query.isLoading ? <div className="audit-loading"><Skeleton height="48px" /><Skeleton height="48px" /><Skeleton height="48px" /></div> :
          query.isError ? <ErrorState message="Unable to load audit sessions." /> :
          <Table columns={columns} rows={query.data ?? []} rowId={(row) => row.id} onRowClick={(row) => navigate(`/audit/${row.id}`)}
            caption="Audit trace sessions" emptyState={<EmptyState icon={<Activity />} title="No trace sessions" description="Run a workflow to create its first complete audit trace." />} />}
      </section>
    </main>
  );
}
