/* 3E — labelled typed I/O value (json | text | file). */
import TypedValueViewer from "./TypedValueViewer";

export interface NodeIoViewerProps {
  label: string;
  value: unknown;
}

export default function NodeIoViewer({ label, value }: NodeIoViewerProps) {
  return (
    <div style={{ marginBottom: "var(--space-3)" }}>
      <div
        className="text-body"
        style={{ color: "var(--color-text-tertiary)", marginBottom: "var(--space-1)" }}
      >
        {label}
      </div>
      <TypedValueViewer value={value} />
    </div>
  );
}
