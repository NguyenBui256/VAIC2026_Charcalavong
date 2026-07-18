/* 3C — shown to a target node's approver when a rollback to that node is
 * pending: Accept (re-run subtree) / Refuse (rejecting node must Approve/
 * Retry/Override instead).
 */
import { Button, Card } from "../../ui";
import type { RollbackRequest } from "../../../lib/runsApi";

export interface RollbackConfirmCardProps {
  rollback: RollbackRequest;
  onConfirm: (accept: boolean) => void;
  pending: boolean;
}

export default function RollbackConfirmCard({
  rollback,
  onConfirm,
  pending,
}: RollbackConfirmCardProps) {
  return (
    <Card>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        <strong className="text-body">
          Rollback requested to this node
        </strong>
        <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          From node “{rollback.requester_node_key}”. Reason:{" "}
          {rollback.reason || "—"}
        </span>
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button
            variant="primary"
            disabled={pending}
            onClick={() => onConfirm(true)}
          >
            Accept
          </Button>
          <Button
            variant="secondary"
            disabled={pending}
            onClick={() => onConfirm(false)}
          >
            Refuse
          </Button>
        </div>
      </div>
    </Card>
  );
}
