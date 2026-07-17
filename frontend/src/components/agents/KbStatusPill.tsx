/* Story 2.4 — KB document status pill (Processing/Indexed/Failed).
 *
 * Processing/Indexed/Failed is NOT part of the locked RunState `stateMapping`
 * (UX-DR11) -- built as a standalone pill from design tokens, mirroring the
 * Story 2.2 `AgentStatusPill` decision (do NOT extend the locked mapping).
 */

import { Loader, Check, XCircle } from "lucide-react";
import { ICON_STROKE_WIDTH } from "../../lib/icons";
import { Tooltip } from "../ui";
import type { KbStatus } from "../../lib/kbApi";

export interface KbStatusPillProps {
  status: KbStatus;
  /** Shown in a tooltip for failed docs, e.g. "Timeout" -> "Failed: Timeout". */
  failureReason?: string | null;
}

export default function KbStatusPill({ status, failureReason }: KbStatusPillProps) {
  if (status === "processing") {
    return (
      <span
        className="vaic-pill"
        style={{ background: "var(--color-running-soft)", color: "var(--color-running)" }}
        role="status"
        data-testid="vaic-kb-pill-processing"
      >
        <Loader size={12} strokeWidth={ICON_STROKE_WIDTH} className="vaic-anim-spin" aria-hidden="true" />
        <span>Processing</span>
      </span>
    );
  }

  if (status === "indexed") {
    return (
      <span
        className="vaic-pill"
        style={{ background: "var(--color-success-soft)", color: "var(--color-success)" }}
        role="status"
        data-testid="vaic-kb-pill-indexed"
      >
        <Check size={12} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
        <span>Indexed</span>
      </span>
    );
  }

  const label = failureReason ? `Failed: ${failureReason}` : "Failed";
  const pill = (
    <span
      className="vaic-pill"
      style={{ background: "var(--color-destructive-soft)", color: "var(--color-destructive)" }}
      role="status"
      data-testid="vaic-kb-pill-failed"
    >
      <XCircle size={12} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
      <span>{label}</span>
    </span>
  );

  return failureReason ? <Tooltip label={failureReason}>{pill}</Tooltip> : pill;
}
