/* 3C — review panel for the selected node. Read-only I/O + history for all;
 * decision actions only when the current user is an approver AND the node is
 * awaiting_approval. Reject offers a parent picker (parents disabled if the
 * rollback to them was already refused).
 */
import { useState } from "react";
import { Button, Card, useToast } from "../../ui";
import NodeIoViewer from "./NodeIoViewer";
import RollbackConfirmCard from "./RollbackConfirmCard";
import RunStatusBadge from "./RunStatusBadge";
import { parentsOf, type MergedNode } from "./mergeNodes";
import type {
  DecisionRequest,
  GraphEdge,
  RollbackRequest,
} from "../../../lib/runsApi";
import type { UseRunMutationsResult } from "../../../hooks/useRunMutations";

export interface RunReviewPanelProps {
  node: MergedNode | null;
  edges: GraphEdge[];
  rollbacks: { pending: RollbackRequest[]; refused: RollbackRequest[] };
  currentUserId: string | undefined;
  mutations: UseRunMutationsResult;
}

export default function RunReviewPanel({
  node,
  edges,
  rollbacks,
  currentUserId,
  mutations,
}: RunReviewPanelProps) {
  const toast = useToast();
  const [guidance, setGuidance] = useState("");
  const [overrideText, setOverrideText] = useState("{}");
  const [reason, setReason] = useState("");
  const [target, setTarget] = useState("");

  if (!node) {
    return (
      <Card>
        <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          Select a node to review it.
        </span>
      </Card>
    );
  }

  const exec = node.exec;
  const status = exec?.status ?? "pending";
  const isApprover = Boolean(
    currentUserId && node.approver_user_ids.includes(currentUserId),
  );
  const canDecide = isApprover && status === "awaiting_approval";
  const parents = parentsOf(node.node_key, edges);
  const refusedParents = new Set(
    rollbacks.refused
      .filter((r) => r.requester_node_key === node.node_key)
      .map((r) => r.target_node_key),
  );

  // Pending rollback whose TARGET is this node → this approver confirms it.
  const pendingForThisTarget = rollbacks.pending.find(
    (r) => r.target_node_key === node.node_key,
  );

  function submit(body: DecisionRequest) {
    mutations.decide.mutate(
      { nodeKey: node!.node_key, body },
      {
        onError: (err) => toast.show(err.message, "error"),
      },
    );
  }

  function onOverride() {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(overrideText);
    } catch {
      toast.show("Override must be valid JSON", "error");
      return;
    }
    submit({ action: "override", output: parsed });
  }

  function onReject() {
    if (!target) {
      toast.show("Pick a parent to roll back to", "error");
      return;
    }
    submit({ action: "reject", reason, target_node_key: target });
  }

  const pending = mutations.decide.isPending;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
      <Card>
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <strong className="text-h3">{node.label || node.node_key}</strong>
            <RunStatusBadge status={status} />
          </div>
          <NodeIoViewer label="Input" value={exec?.input} />
          <NodeIoViewer label="Output" value={exec?.output} />
          {exec?.decision && (
            <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
              Last decision: {exec.decision}
              {exec.reason ? ` — ${exec.reason}` : ""}
            </span>
          )}
        </div>
      </Card>

      {pendingForThisTarget && isApprover && (
        <RollbackConfirmCard
          rollback={pendingForThisTarget}
          pending={mutations.confirm.isPending}
          onConfirm={(accept) =>
            mutations.confirm.mutate(
              { rollbackId: pendingForThisTarget.id, accept },
              {
                onError: (err) => toast.show(err.message, "error"),
              },
            )
          }
        />
      )}

      {canDecide && (
        <Card>
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <div style={{ display: "flex", gap: "var(--space-2)" }}>
              <Button variant="primary" disabled={pending} onClick={() => submit({ action: "approve" })}>
                Approve
              </Button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              <label className="text-body">Retry guidance</label>
              <textarea
                className="vaic-form-input vaic-focusable"
                value={guidance}
                onChange={(e) => setGuidance(e.target.value)}
                rows={2}
              />
              <Button
                variant="secondary"
                disabled={pending}
                onClick={() => submit({ action: "retry", guidance })}
              >
                Retry
              </Button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              <label className="text-body">Override output (JSON)</label>
              <textarea
                className="vaic-form-input vaic-focusable"
                value={overrideText}
                onChange={(e) => setOverrideText(e.target.value)}
                rows={3}
              />
              <Button variant="secondary" disabled={pending} onClick={onOverride}>
                Override
              </Button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
              <label className="text-body">Reject → roll back to parent</label>
              <select
                className="vaic-form-input vaic-focusable"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
              >
                <option value="">Select a parent…</option>
                {parents.map((p) => (
                  <option key={p} value={p} disabled={refusedParents.has(p)}>
                    {p}
                    {refusedParents.has(p) ? " (refused)" : ""}
                  </option>
                ))}
              </select>
              <textarea
                className="vaic-form-input vaic-focusable"
                placeholder="Reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
              />
              <Button variant="destructive" disabled={pending} onClick={onReject}>
                Reject
              </Button>
            </div>
          </div>
        </Card>
      )}

      {!canDecide && status === "awaiting_approval" && !isApprover && (
        <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          Awaiting another approver's decision.
        </span>
      )}
    </div>
  );
}
