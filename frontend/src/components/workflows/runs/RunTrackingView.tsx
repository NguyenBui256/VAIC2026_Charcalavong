/* 3C — run tracking: loads topology once + polls node state, merges by
 * node_key, renders the SVG canvas beside the review panel. Selecting a node
 * opens its review. Auto-selects the node awaiting approval.
 */
import { useEffect, useMemo, useState } from "react";
import { ErrorState, Skeleton } from "../../ui";
import RunGraphCanvas from "./RunGraphCanvas";
import RunReviewPanel from "./RunReviewPanel";
import RunStatusBadge from "./RunStatusBadge";
import { mergeNodes } from "./mergeNodes";
import { useRun, useRunGraph, useRunNodes } from "../../../hooks/useRunTracking";
import { useRunMutations } from "../../../hooks/useRunMutations";
import { useAuth } from "../../../hooks/useAuth";

export interface RunTrackingViewProps {
  runId: string;
}

export default function RunTrackingView({ runId }: RunTrackingViewProps) {
  const { user } = useAuth();
  const run = useRun(runId);
  const graph = useRunGraph(runId);
  const nodes = useRunNodes(runId, run.data?.status);
  const mutations = useRunMutations(runId);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  const merged = useMemo(() => {
    if (!graph.data || !nodes.data) return [];
    return mergeNodes(graph.data.nodes, nodes.data.nodes);
  }, [graph.data, nodes.data]);

  // Auto-select the first node awaiting approval when nothing is selected.
  useEffect(() => {
    if (selectedKey) return;
    const awaiting = merged.find((n) => n.exec?.status === "awaiting_approval");
    if (awaiting) setSelectedKey(awaiting.node_key);
  }, [merged, selectedKey]);

  if (run.isError || graph.isError) {
    return (
      <ErrorState
        message={
          run.error?.message ?? graph.error?.message ?? "Failed to load run"
        }
      />
    );
  }
  if (run.isLoading || graph.isLoading) {
    return <Skeleton lines={6} height="24px" />;
  }

  const pendingRollbackKeys = new Set(
    (nodes.data?.rollbacks.pending ?? []).map((r) => r.target_node_key),
  );
  const selected = merged.find((n) => n.node_key === selectedKey) ?? null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <strong className="text-h2">Run</strong>
        {run.data && <RunStatusBadge status={run.data.status} />}
      </div>
      <div style={{ display: "flex", gap: "var(--space-4)", alignItems: "flex-start" }}>
        <div style={{ flex: 1, overflow: "auto", border: "1px solid var(--color-border)", borderRadius: "var(--radius-md, 8px)" }}>
          <RunGraphCanvas
            nodes={merged}
            edges={graph.data?.edges ?? []}
            selectedKey={selectedKey}
            onSelect={setSelectedKey}
            pendingRollbackKeys={pendingRollbackKeys}
          />
        </div>
        <div style={{ width: 360, flexShrink: 0 }}>
          <RunReviewPanel
            node={selected}
            edges={graph.data?.edges ?? []}
            rollbacks={nodes.data?.rollbacks ?? { pending: [], refused: [] }}
            currentUserId={user?.id}
            mutations={mutations}
          />
        </div>
      </div>
    </div>
  );
}
