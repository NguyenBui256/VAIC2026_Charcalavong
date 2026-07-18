/* Outputs section of the chat side panel — SAMPLE data only.
 * Placeholder list of result files until real run outputs are wired.
 */

import { FileText } from "lucide-react";

interface SampleOutput {
  name: string;
  type: string;
  size: string;
}

const SAMPLE_OUTPUTS: SampleOutput[] = [
  { name: "report-summary.pdf", type: "PDF", size: "182 KB" },
  { name: "analysis-data.csv", type: "CSV", size: "44 KB" },
];

export default function OutputsPanel() {
  return (
    <div>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        {SAMPLE_OUTPUTS.map((file) => (
          <div
            key={file.name}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-2)",
              padding: "var(--space-2)",
              borderRadius: "var(--radius-control, 8px)",
              border: "1px solid var(--color-border)",
            }}
          >
            <FileText size={15} strokeWidth={1.5} style={{ flexShrink: 0, color: "var(--color-text-tertiary)" }} />
            <span
              style={{
                flex: 1,
                minWidth: 0,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                fontSize: "var(--text-body)",
              }}
            >
              {file.name}
            </span>
            <span
              className="text-caption"
              style={{
                padding: "0 var(--space-2)",
                borderRadius: "var(--radius-control, 4px)",
                background: "var(--color-surface-muted)",
                color: "var(--color-text-secondary)",
              }}
            >
              {file.type}
            </span>
            <span
              className="text-caption"
              style={{ color: "var(--color-text-tertiary)", flexShrink: 0 }}
            >
              {file.size}
            </span>
          </div>
        ))}
      </div>
      <p
        className="text-caption"
        style={{ color: "var(--color-text-tertiary)", marginTop: "var(--space-3)" }}
      >
        Sample data
      </p>
    </div>
  );
}
