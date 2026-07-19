/* 3E — render a stored I/O value by its type: json (pre), text (plain), file
 * (authed download button). Legacy/agent dicts normalize to json via toTyped.
 */
import { Button, useToast } from "../../ui";
import { downloadWorkflowFile, toTyped } from "../../../lib/typedValue";

export interface TypedValueViewerProps {
  value: unknown;
}

export default function TypedValueViewer({ value }: TypedValueViewerProps) {
  const toast = useToast();
  if (value == null) {
    return <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>—</span>;
  }
  const tv = toTyped(value);

  if (tv.type === "file") {
    return (
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
        <Button
          variant="secondary"
          onClick={() =>
            downloadWorkflowFile(tv).catch((e) =>
              toast.show((e as Error).message, "error"),
            )
          }
        >
          Download {tv.name}
        </Button>
        <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          {tv.mime} · {(tv.size / 1024).toFixed(1)} KB
        </span>
      </div>
    );
  }

  const text =
    tv.type === "text" ? tv.value : JSON.stringify(tv.value, null, 2);
  return (
    <pre
      style={{
        margin: 0,
        padding: "var(--space-2)",
        background: "var(--color-surface-inset, var(--color-surface))",
        borderRadius: "var(--radius-control, 6px)",
        overflow: "auto",
        maxHeight: 200,
        fontSize: "0.85em",
        whiteSpace: "pre-wrap",
      }}
    >
      {text}
    </pre>
  );
}
