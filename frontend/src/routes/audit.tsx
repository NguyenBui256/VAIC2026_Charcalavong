/* Epic 6 (FR-22) — Trace Dashboard (/audit).
 *
 * Renders the tenant's Audit Trail as a timeline (the bar-4 demo screen).
 * Independent of the Orchestrator: it reads whatever audit_trail rows exist.
 * Deep-linkable per Run via `/audit?run_id=<id>` (a Run's ordered timeline).
 */

import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Button, EmptyState, ErrorState, Skeleton, useToast } from "../components/ui";
import TraceTimeline from "../components/audit/TraceTimeline";
import CollaborationGraph from "../components/audit/CollaborationGraph";
import { useAuditTrail } from "../hooks/useAuditTrail";
import { useAgents } from "../hooks/useAgents";
import { useDebounce } from "../lib/useDebounce";
import { buildCollaborationGraph } from "../lib/collaborationGraph";
import { downloadAuditExport, type AuditExportFormat } from "../lib/auditApi";
import { semanticIcons, ICON_STROKE_WIDTH } from "../lib/icons";

type TraceView = "timeline" | "graph";

const TYPE_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All types" },
  { value: "decomposition", label: "Decomposition" },
  { value: "task_dispatch", label: "Task dispatch" },
  { value: "tool_call", label: "Tool call" },
  { value: "model_invocation", label: "Model invocation" },
  { value: "aggregation", label: "Aggregation" },
  { value: "escalation", label: "Escalation" },
  { value: "workflow_run.transition", label: "Run transition" },
];

export default function AuditPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const runIdParam = searchParams.get("run_id") ?? "";

  const [runIdInput, setRunIdInput] = useState(runIdParam);
  const [type, setType] = useState("");
  const [view, setView] = useState<TraceView>("timeline");
  const [exporting, setExporting] = useState(false);
  const debouncedRunId = useDebounce(runIdInput, 300);
  const toast = useToast();

  const query = useAuditTrail({
    run_id: debouncedRunId.trim() || undefined,
    type: type || undefined,
  });
  const { data, isLoading, isError } = query;
  const entries = useMemo(() => data ?? [], [data]);
  const TraceIcon = semanticIcons.Trace;

  // agent_id → name map for nicer collaboration-graph labels (Epic 2 data).
  const { data: agentsData } = useAgents({});
  const nameById = useMemo(() => {
    const map = new Map<string, string>();
    (agentsData ?? []).forEach((a) => map.set(a.id, a.name));
    return map;
  }, [agentsData]);
  const graph = useMemo(
    () => buildCollaborationGraph(entries, nameById),
    [entries, nameById],
  );

  async function handleExport(format: AuditExportFormat) {
    setExporting(true);
    try {
      await downloadAuditExport(
        { run_id: debouncedRunId.trim() || undefined, type: type || undefined },
        format,
      );
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Export failed", "error");
    } finally {
      setExporting(false);
    }
  }

  function updateRunId(value: string) {
    setRunIdInput(value);
    const next = new URLSearchParams(searchParams);
    if (value.trim()) next.set("run_id", value.trim());
    else next.delete("run_id");
    setSearchParams(next, { replace: true });
  }

  function renderBody() {
    if (isError) {
      return (
        <ErrorState
          message={query.error?.message ?? "Failed to load the Audit Trail"}
          retry={
            <Button variant="secondary" onClick={() => query.refetch()}>
              Retry
            </Button>
          }
        />
      );
    }
    if (isLoading) {
      return (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
          <Skeleton height="72px" />
          <Skeleton height="72px" />
          <Skeleton height="72px" />
        </div>
      );
    }
    if (entries.length === 0) {
      return (
        <EmptyState
          icon={<TraceIcon size={48} strokeWidth={ICON_STROKE_WIDTH} />}
          title="No audit entries"
          description={
            debouncedRunId || type
              ? "No entries match the current filters."
              : "Steps appear here as Agents and Workflows run."
          }
        />
      );
    }
    if (view === "graph") {
      return (
        <div>
          {!debouncedRunId && (
            <p
              className="text-caption"
              style={{ color: "var(--color-text-tertiary)", marginBottom: "var(--space-3)" }}
            >
              Showing agents across all runs — filter by Run id for one workflow's
              collaboration.
            </p>
          )}
          <CollaborationGraph graph={graph} />
        </div>
      );
    }
    return <TraceTimeline entries={entries} />;
  }

  return (
    <div data-testid="vaic-audit-page">
      <header
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: "var(--space-3)",
          marginBottom: "var(--space-4)",
        }}
      >
        <div>
          <h1 className="text-h1" style={{ marginBottom: "var(--space-1)" }}>
            Trace Dashboard
          </h1>
          <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
            Per-step Audit Trail — every decomposition, dispatch, tool call, model
            invocation and aggregation, in order.
          </p>
        </div>
        <div role="tablist" aria-label="Trace view" style={{ display: "flex", gap: "var(--space-1)" }}>
          <Button
            variant={view === "timeline" ? "primary" : "ghost"}
            onClick={() => setView("timeline")}
            aria-pressed={view === "timeline"}
          >
            Timeline
          </Button>
          <Button
            variant={view === "graph" ? "primary" : "ghost"}
            onClick={() => setView("graph")}
            aria-pressed={view === "graph"}
          >
            Graph
          </Button>
        </div>
      </header>

      <div
        className="vaic-agents-filters"
        style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}
      >
        <input
          type="search"
          aria-label="Filter by Run id"
          placeholder="Filter by Run id"
          className="vaic-form-input vaic-focusable"
          value={runIdInput}
          onChange={(e) => updateRunId(e.target.value)}
        />
        <select
          aria-label="Filter by entry type"
          className="vaic-form-input vaic-focusable"
          value={type}
          onChange={(e) => setType(e.target.value)}
        >
          {TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        <span style={{ flex: 1 }} />
        <Button
          variant="ghost"
          onClick={() => handleExport("json")}
          disabled={exporting || entries.length === 0}
        >
          Export JSON
        </Button>
        <Button
          variant="ghost"
          onClick={() => handleExport("csv")}
          disabled={exporting || entries.length === 0}
        >
          Export CSV
        </Button>
      </div>

      {renderBody()}
    </div>
  );
}
