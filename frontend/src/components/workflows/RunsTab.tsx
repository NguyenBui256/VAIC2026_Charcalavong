/* 3C — Runs tab: trigger a run (JSON input → POST /workflows/{id}/runs) and
 * list existing runs (row → the tracking page).
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Button, Table, EmptyState, ErrorState, Skeleton, useToast } from "../ui";
import type { TableColumn } from "../ui";
import RunStatusBadge from "./runs/RunStatusBadge";
import { useRuns } from "../../hooks/useRuns";
import { createRun, type Run } from "../../lib/runsApi";

export interface RunsTabProps {
  workflowId: string;
}

export default function RunsTab({ workflowId }: RunsTabProps) {
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data: runs, isLoading, isError, error, refetch } = useRuns(workflowId);
  const [inputText, setInputText] = useState("{}");
  const [creating, setCreating] = useState(false);

  async function onCreate() {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(inputText);
    } catch {
      toast.show("Input must be valid JSON", "error");
      return;
    }
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      toast.show("Input must be a JSON object", "error");
      return;
    }
    setCreating(true);
    try {
      const run = await createRun(workflowId, parsed);
      queryClient.invalidateQueries({ queryKey: ["runs", workflowId] });
      navigate(`/workflows/${workflowId}/runs/${run.id}`);
    } catch (e) {
      toast.show((e as Error).message, "error");
    } finally {
      setCreating(false);
    }
  }

  const columns: TableColumn<Run>[] = [
    {
      key: "status",
      header: "Status",
      render: (row) => <RunStatusBadge status={row.status} />,
    },
    {
      key: "created_at",
      header: "Created",
      render: (row) => new Date(row.created_at).toLocaleString(),
    },
    {
      key: "ended_at",
      header: "Ended",
      render: (row) => (row.ended_at ? new Date(row.ended_at).toLocaleString() : "—"),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <label className="text-body">New run input (JSON)</label>
        <textarea
          className="vaic-form-input vaic-focusable"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          rows={3}
        />
        <div>
          <Button variant="primary" disabled={creating} onClick={onCreate}>
            Run
          </Button>
        </div>
      </div>

      {isError ? (
        <ErrorState
          message={error?.message ?? "Failed to load runs"}
          retry={
            <Button variant="secondary" onClick={() => refetch()}>
              Retry
            </Button>
          }
        />
      ) : isLoading ? (
        <Skeleton height="40px" />
      ) : (
        <Table
          columns={columns}
          rows={runs ?? []}
          rowId={(row) => row.id}
          onRowClick={(row) => navigate(`/workflows/${workflowId}/runs/${row.id}`)}
          emptyState={<EmptyState title="No runs yet." description="Trigger a run above." />}
        />
      )}
    </div>
  );
}
