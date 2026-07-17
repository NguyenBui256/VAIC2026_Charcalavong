/* Story 2.2 — Agent status pill (Draft/Active).
 *
 * Agent `status` is Draft|Active, which is NOT in the locked RunState set
 * (pending|running|success|error|escalated|draft). Draft reuses StatusPill
 * (state="draft"); Active is a dedicated emerald pill built from
 * --color-success so the locked stateMapping stays untouched (UX-DR11).
 */

import { Check } from "lucide-react";
import { ICON_STROKE_WIDTH } from "../../lib/icons";
import { StatusPill } from "../ui";
import type { AgentStatus } from "../../lib/agentsApi";

export interface AgentStatusPillProps {
  status: AgentStatus;
}

export default function AgentStatusPill({ status }: AgentStatusPillProps) {
  if (status === "draft") {
    return <StatusPill state="draft" />;
  }

  return (
    <span
      className="vaic-pill"
      style={{ background: "var(--color-success-soft)", color: "var(--color-success)" }}
      role="status"
      data-testid="vaic-pill-active"
    >
      <Check size={12} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
      <span>Active</span>
    </span>
  );
}
