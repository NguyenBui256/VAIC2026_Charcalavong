/* Epic 6 (FR-22) — vertical Trace timeline: a rail of TraceEntryCards. */

import TraceEntryCard from "./TraceEntryCard";
import type { AuditEntry } from "../../lib/auditApi";

export interface TraceTimelineProps {
  entries: AuditEntry[];
}

export default function TraceTimeline({ entries }: TraceTimelineProps) {
  return (
    <div data-testid="vaic-trace-timeline">
      {entries.map((entry, index) => (
        <TraceEntryCard
          key={entry.id}
          entry={entry}
          isLast={index === entries.length - 1}
        />
      ))}
    </div>
  );
}
