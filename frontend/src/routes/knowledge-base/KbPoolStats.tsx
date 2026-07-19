/* Overview stat strip for the Knowledge Base pool. Keeps the dashboard KPI
 * visual language (tabular-nums value + labelled icon) but adds a tinted icon
 * chip, a left accent bar, hover lift, and a derived context hint per metric
 * so the strip reads richer without leaving the design system. All figures are
 * derived from the loaded documents — no extra fetch. */

import type { CSSProperties, ReactNode } from "react";
import { Files, CircleCheck, Loader, Database } from "lucide-react";
import { ICON_STROKE_WIDTH } from "../../lib/icons";
import { formatBytes } from "./kb-file-presentation";
import type { KbDocument } from "../../lib/kbApi";

/* Hover lift, left accent bar and the processing pulse can't be expressed as
 * React inline styles (:hover / ::before / @keyframes), so they live here.
 * Per-card colour is passed in via the --stat-accent* custom properties. */
const STYLES = `
.vaic-kb-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.vaic-kb-stat {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  transition: transform var(--duration-hover) ease-out,
              border-color var(--duration-hover) ease-out,
              box-shadow var(--duration-hover) ease-out;
}
.vaic-kb-stat::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: var(--stat-accent);
}
.vaic-kb-stat:hover {
  transform: translateY(-2px);
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-md);
}
.vaic-kb-stat-chip {
  display: inline-grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  color: var(--stat-accent);
  background: var(--stat-accent-soft);
}
.vaic-kb-stat-value {
  display: block;
  font-variant-numeric: tabular-nums;
  font-size: 30px;
  font-weight: 600;
  line-height: 1.1;
  color: var(--color-text);
}
.vaic-kb-stat-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: var(--space-2);
}
.vaic-kb-stat-label { font-weight: 600; color: var(--color-text-secondary); }
.vaic-kb-stat-hint {
  display: inline-flex;
  align-items: center;
  color: var(--color-text-tertiary);
}
.vaic-kb-stat-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 6px;
  border-radius: 50%;
  background: var(--stat-accent);
  animation: vaic-kb-pulse 1.4s ease-in-out infinite;
}
@keyframes vaic-kb-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.35; transform: scale(0.65); }
}
@media (prefers-reduced-motion: reduce) {
  .vaic-kb-stat { transition: none; }
  .vaic-kb-stat:hover { transform: none; }
  .vaic-kb-stat-dot { animation: none; }
}
`;

interface StatCardProps {
  accent: string;
  soft: string;
  icon: ReactNode;
  value: ReactNode;
  label: string;
  hint: ReactNode;
}

function StatCard({ accent, soft, icon, value, label, hint }: StatCardProps) {
  const style = {
    "--stat-accent": accent,
    "--stat-accent-soft": soft,
  } as CSSProperties;
  return (
    <div className="vaic-kb-stat" style={style}>
      <span className="vaic-kb-stat-chip">{icon}</span>
      <div>
        <span className="vaic-kb-stat-value">{value}</span>
        <div className="text-small vaic-kb-stat-meta">
          <span className="vaic-kb-stat-label">{label}</span>
          <span className="vaic-kb-stat-hint">{hint}</span>
        </div>
      </div>
    </div>
  );
}

export default function KbPoolStats({ documents }: { documents: KbDocument[] }) {
  const total = documents.length;
  const indexed = documents.filter((d) => d.status === "indexed").length;
  const processing = documents.filter((d) => d.status === "processing").length;
  const totalBytes = documents.reduce((sum, d) => sum + d.size_bytes, 0);

  const indexedPct = total > 0 ? Math.round((indexed / total) * 100) : 0;
  const iconProps = { size: 18, strokeWidth: ICON_STROKE_WIDTH, "aria-hidden": true } as const;

  return (
    <section data-testid="vaic-kb-stats" className="vaic-kb-stats">
      <style>{STYLES}</style>

      <StatCard
        accent="var(--color-primary)"
        soft="var(--color-primary-soft)"
        icon={<Files {...iconProps} />}
        value={total}
        label="Documents"
        hint="in the pool"
      />
      <StatCard
        accent="var(--color-success)"
        soft="var(--color-success-soft)"
        icon={<CircleCheck {...iconProps} />}
        value={indexed}
        label="Indexed"
        hint={total > 0 ? `${indexedPct}% of pool ready` : "—"}
      />
      <StatCard
        accent="var(--color-running)"
        soft="var(--color-running-soft)"
        icon={<Loader {...iconProps} />}
        value={processing}
        label="Processing"
        hint={
          processing > 0 ? (
            <>
              <span className="vaic-kb-stat-dot" aria-hidden="true" />
              in progress
            </>
          ) : (
            "up to date"
          )
        }
      />
      <StatCard
        accent="var(--color-text-secondary)"
        soft="var(--color-surface-muted)"
        icon={<Database {...iconProps} />}
        value={formatBytes(totalBytes)}
        label="Total size"
        hint={total > 0 ? `avg ${formatBytes(totalBytes / total)} / doc` : "—"}
      />
    </section>
  );
}
