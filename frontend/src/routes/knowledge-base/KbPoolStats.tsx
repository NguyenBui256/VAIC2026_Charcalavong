/* Overview stat strip for the Knowledge Base pool. Mirrors the dashboard
 * KpiStrip visual language (tabular-nums value + labelled icon) so the two
 * surfaces read as one system. Derived entirely from the loaded documents —
 * no extra fetch. */

import type { CSSProperties, ReactNode } from "react";
import { Files, CircleCheck, Loader, Database } from "lucide-react";
import { Card } from "../../components/ui";
import { ICON_STROKE_WIDTH } from "../../lib/icons";
import { formatBytes } from "./kb-file-presentation";
import type { KbDocument } from "../../lib/kbApi";

const valueStyle: CSSProperties = {
  fontVariantNumeric: "tabular-nums",
  fontSize: "28px",
  fontWeight: 600,
  color: "var(--color-text)",
  lineHeight: 1.2,
  display: "block",
};

const labelStyle: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "var(--space-1)",
  color: "var(--color-text-tertiary)",
};

function StatCard({ label, value, icon }: { label: string; value: ReactNode; icon: ReactNode }) {
  return (
    <Card>
      <span style={valueStyle}>{value}</span>
      <span className="text-small" style={labelStyle}>
        {icon}
        {label}
      </span>
    </Card>
  );
}

export default function KbPoolStats({ documents }: { documents: KbDocument[] }) {
  const indexed = documents.filter((d) => d.status === "indexed").length;
  const processing = documents.filter((d) => d.status === "processing").length;
  const totalBytes = documents.reduce((sum, d) => sum + d.size_bytes, 0);

  const wrapperStyle: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "var(--space-3)",
    marginBottom: "var(--space-4)",
  };

  const iconProps = { size: 14, strokeWidth: ICON_STROKE_WIDTH, "aria-hidden": true } as const;

  return (
    <section data-testid="vaic-kb-stats" style={wrapperStyle}>
      <StatCard label="Documents" value={documents.length} icon={<Files {...iconProps} />} />
      <StatCard
        label="Indexed"
        value={indexed}
        icon={<CircleCheck {...iconProps} color="var(--color-success)" />}
      />
      <StatCard
        label="Processing"
        value={processing}
        icon={<Loader {...iconProps} color="var(--color-running)" />}
      />
      <StatCard label="Total size" value={formatBytes(totalBytes)} icon={<Database {...iconProps} />} />
    </section>
  );
}
