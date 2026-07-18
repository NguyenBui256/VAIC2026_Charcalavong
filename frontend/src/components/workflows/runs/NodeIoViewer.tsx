/* 3C — read-only JSON view of a node's input/output. */
export interface NodeIoViewerProps {
  label: string;
  value: unknown;
}

export default function NodeIoViewer({ label, value }: NodeIoViewerProps) {
  const text =
    value == null ? "—" : JSON.stringify(value, null, 2);
  return (
    <div style={{ marginBottom: "var(--space-3)" }}>
      <div
        className="text-body"
        style={{ color: "var(--color-text-tertiary)", marginBottom: "var(--space-1)" }}
      >
        {label}
      </div>
      <pre
        style={{
          margin: 0,
          padding: "var(--space-2)",
          background: "var(--color-surface-inset, var(--color-surface))",
          borderRadius: "var(--radius-control, 6px)",
          overflow: "auto",
          maxHeight: 200,
          fontSize: "0.85em",
        }}
      >
        {text}
      </pre>
    </div>
  );
}
