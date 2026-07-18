/* 3C/3E — target node's approver confirms a pending rollback: Accept (re-run
 * subtree) or Refuse (with an optional reason shown back to the rejecter).
 */
import { useState } from "react";
import { Button, Card } from "../../ui";
import type { RollbackRequest } from "../../../lib/runsApi";

export interface RollbackConfirmCardProps {
  rollback: RollbackRequest;
  onConfirm: (accept: boolean, reason?: string) => void;
  pending: boolean;
}

export default function RollbackConfirmCard({
  rollback,
  onConfirm,
  pending,
}: RollbackConfirmCardProps) {
  const [reason, setReason] = useState("");
  return (
    <Card>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        <strong className="text-body">Rollback requested to this node</strong>
        <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          From node “{rollback.requester_node_key}”. Reason: {rollback.reason || "—"}
        </span>
        <textarea
          className="vaic-form-input vaic-focusable"
          placeholder="Reason (shown to the requester if you refuse)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={2}
        />
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button variant="primary" disabled={pending} onClick={() => onConfirm(true)}>
            Accept
          </Button>
          <Button
            variant="secondary"
            disabled={pending}
            onClick={() => onConfirm(false, reason)}
          >
            Refuse
          </Button>
        </div>
      </div>
    </Card>
  );
}
