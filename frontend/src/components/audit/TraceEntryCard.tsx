/* Epic 6 (FR-22) — one Trace timeline entry.
 *
 * Renders a type-colored dot on the timeline rail + a card with the entry
 * header (type, agent, latency, timestamp) that expands to reveal the raw
 * input/output JSON (CodeBlock). This is the per-step Audit Trail row the
 * bar-4 demo is scored on.
 */

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { CodeBlock } from "../ui";
import { ICON_STROKE_WIDTH, semanticIcons } from "../../lib/icons";
import { auditEntryMeta } from "../../lib/auditEntryMeta";
import type { AuditEntry } from "../../lib/auditApi";

export interface TraceEntryCardProps {
  entry: AuditEntry;
  /** Last row hides the connecting rail below its dot. */
  isLast: boolean;
}

function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(ms < 10_000 ? 2 : 1)} s`;
}

export default function TraceEntryCard({ entry, isLast }: TraceEntryCardProps) {
  const [open, setOpen] = useState(false);
  const meta = auditEntryMeta(entry.type);
  const Icon = meta.icon;
  const AgentIcon = semanticIcons.Agent;
  const Chevron = open ? ChevronDown : ChevronRight;

  const hasDetail =
    Object.keys(entry.input ?? {}).length > 0 ||
    Object.keys(entry.output ?? {}).length > 0;

  return (
    <div style={{ display: "flex", gap: "var(--space-3)" }}>
      {/* Timeline rail: dot + connecting line. */}
      <div
        style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 28 }}
        aria-hidden="true"
      >
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            width: 28,
            height: 28,
            borderRadius: "50%",
            background: "var(--color-surface)",
            border: `2px solid ${meta.colorVar}`,
            color: meta.colorVar,
            flexShrink: 0,
          }}
        >
          <Icon size={14} strokeWidth={ICON_STROKE_WIDTH} />
        </span>
        {!isLast && (
          <span style={{ flex: 1, width: 2, background: "var(--color-border)", marginTop: 2 }} />
        )}
      </div>

      {/* Content card. */}
      <div
        className="vaic-card"
        style={{ flex: 1, marginBottom: "var(--space-3)", padding: "var(--space-3)" }}
      >
        <button
          type="button"
          onClick={() => hasDetail && setOpen((v) => !v)}
          className="vaic-focusable"
          aria-expanded={open}
          disabled={!hasDetail}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
            width: "100%",
            background: "none",
            border: "none",
            padding: 0,
            cursor: hasDetail ? "pointer" : "default",
            textAlign: "left",
            color: "inherit",
          }}
        >
          {hasDetail ? (
            <Chevron size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
          ) : (
            <span style={{ width: 16 }} />
          )}
          <span style={{ fontWeight: 600, color: meta.colorVar }}>{meta.label}</span>
          <span
            className="vaic-pill"
            style={{ background: "var(--color-surface-muted)", color: "var(--color-text-secondary)" }}
          >
            <AgentIcon size={12} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
            <span style={{ fontFamily: "var(--font-mono)" }}>
              {entry.agent_id ? entry.agent_id.slice(0, 8) : "orchestrator"}
            </span>
          </span>
          <span style={{ flex: 1 }} />
          {entry.latency_ms > 0 && (
            <span className="text-caption" style={{ color: "var(--color-text-tertiary)" }}>
              {formatLatency(entry.latency_ms)}
            </span>
          )}
          <span className="text-caption" style={{ color: "var(--color-text-tertiary)" }}>
            {entry.ts ? new Date(entry.ts).toLocaleTimeString() : "—"}
          </span>
        </button>

        {open && hasDetail && (
          <div style={{ marginTop: "var(--space-3)", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            {entry.model && (
              <div className="text-caption" style={{ color: "var(--color-text-tertiary)" }}>
                Model: <span style={{ fontFamily: "var(--font-mono)" }}>{entry.model}</span>
              </div>
            )}
            <DetailBlock label="Input" value={entry.input} />
            <DetailBlock label="Output" value={entry.output} />
          </div>
        )}
      </div>
    </div>
  );
}

function DetailBlock({ label, value }: { label: string; value: Record<string, unknown> }) {
  if (!value || Object.keys(value).length === 0) return null;
  return (
    <div>
      <div className="text-caption" style={{ color: "var(--color-text-tertiary)", marginBottom: "var(--space-1)" }}>
        {label}
      </div>
      <CodeBlock code={JSON.stringify(value, null, 2)} language="json" />
    </div>
  );
}
