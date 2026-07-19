import StatusPill from "../../components/ui/StatusPill";
import type { RunState } from "../../lib/icons";
import type { AuditStatus } from "./types";

const mapping: Record<AuditStatus, RunState> = {
  pending: "pending", running: "running", awaiting_human: "escalated",
  completed: "success", failed: "error", timed_out: "error",
  cancelled: "error", skipped: "draft",
};

export default function AuditStatusPill({ status }: { status: AuditStatus }) {
  return <StatusPill state={mapping[status]} label={status.replaceAll("_", " ")} />;
}
