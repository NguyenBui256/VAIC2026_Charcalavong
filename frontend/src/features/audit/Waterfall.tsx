import type { AuditSpan } from "./types";
import AuditStatusPill from "./AuditStatus";

export default function Waterfall({ spans, onSelect }: { spans: AuditSpan[]; onSelect: (span: AuditSpan) => void }) {
  if (!spans.length) return <div className="audit-empty">No execution spans recorded.</div>;
  const starts = spans.map((span) => new Date(span.started_at).getTime());
  const min = Math.min(...starts);
  const max = Math.max(...spans.map((span, index) => starts[index] + (span.duration_ms ?? 100)));
  const range = Math.max(1, max - min);
  return (
    <div className="audit-waterfall" role="list" aria-label="Execution waterfall">
      {spans.map((span, index) => {
        const left = ((starts[index] - min) / range) * 100;
        const width = Math.max(1.5, ((span.duration_ms ?? 100) / range) * 100);
        return (
          <button key={span.id} className="audit-waterfall-row" onClick={() => onSelect(span)} role="listitem">
            <span className="audit-waterfall-label"><strong>{span.name}</strong><AuditStatusPill status={span.status} /></span>
            <span className="audit-waterfall-track">
              <span className={`audit-waterfall-bar audit-node-${span.status}`} style={{ left: `${left}%`, width: `${width}%` }} />
            </span>
            <span className="audit-waterfall-time">{span.duration_ms == null ? "live" : `${span.duration_ms} ms`}</span>
          </button>
        );
      })}
    </div>
  );
}
