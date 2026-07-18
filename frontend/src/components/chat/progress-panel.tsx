/* Progress section of the chat side panel — SAMPLE data only.
 * Shows run node status vocabulary (see runsApi NodeStatus) as a
 * placeholder until a real run is wired to a chat conversation.
 */

import type { NodeStatus } from "../../lib/runsApi";

interface SampleStep {
  label: string;
  status: NodeStatus;
}

const SAMPLE_STEPS: SampleStep[] = [
  { label: "Collect data", status: "completed" },
  { label: "Analyze request", status: "running" },
  { label: "Awaiting approval", status: "awaiting_approval" },
  { label: "Compile results", status: "pending" },
];

const STATUS_COLOR: Record<NodeStatus, string> = {
  pending: "var(--color-text-tertiary)",
  running: "var(--color-primary)",
  awaiting_approval: "var(--color-warning, #d97706)",
  completed: "var(--color-success, #16a34a)",
  failed: "var(--color-danger, #dc2626)",
  rejected: "var(--color-danger, #dc2626)",
  skipped: "var(--color-text-tertiary)",
  rolled_back: "var(--color-warning, #d97706)",
};

interface Props {
  targetType: "agent" | "workflow" | null;
}

export default function ProgressPanel({ targetType }: Props) {
  if (targetType !== "workflow") {
    return (
      <p
        className="text-caption"
        style={{ color: "var(--color-text-tertiary)", padding: "var(--space-2) 0" }}
      >
        No run yet — pick a workflow to see progress.
      </p>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        {SAMPLE_STEPS.map((step) => (
          <div
            key={step.label}
            style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}
          >
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: STATUS_COLOR[step.status],
                flexShrink: 0,
              }}
            />
            <span
              style={{ fontSize: "var(--text-body)", color: "var(--color-text-primary)" }}
            >
              {step.label}
            </span>
            <span
              className="text-caption"
              style={{ marginLeft: "auto", color: "var(--color-text-tertiary)" }}
            >
              {step.status}
            </span>
          </div>
        ))}
      </div>
      <p
        className="text-caption"
        style={{ color: "var(--color-text-tertiary)", marginTop: "var(--space-3)" }}
      >
        Sample data (not wired to a real run)
      </p>
    </div>
  );
}
