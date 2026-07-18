/* Knowledge Base document list — a scannable row list (replaces the dense
 * table). Each row: file-type avatar, name + meta line, status pill, delete.
 * Presentation only; data + mutations stay in KnowledgeBasePage.
 */

import { Trash2, FileText } from "lucide-react";
import KbStatusPill from "../agents/KbStatusPill";
import type { KbDocument } from "../../lib/kbApi";

interface Props {
  documents: KbDocument[];
  isBuilder: boolean;
  onDelete: (id: string) => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** File-type label + tinted avatar colors, derived from name / content type. */
function fileMeta(doc: KbDocument): { label: string; bg: string; fg: string } {
  const name = doc.filename.toLowerCase();
  const ext = name.slice(name.lastIndexOf(".") + 1);
  if (ext === "pdf") return { label: "PDF", bg: "rgba(220,38,38,0.10)", fg: "#dc2626" };
  if (ext === "docx" || ext === "doc") return { label: "DOCX", bg: "rgba(37,99,235,0.10)", fg: "#2563eb" };
  if (ext === "md" || ext === "markdown") return { label: "MD", bg: "rgba(13,148,136,0.10)", fg: "#0d9488" };
  if (ext === "txt") return { label: "TXT", bg: "rgba(100,116,139,0.12)", fg: "#475569" };
  return { label: (ext || "FILE").toUpperCase(), bg: "var(--color-surface-muted)", fg: "var(--color-text-secondary)" };
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function KbDocumentList({ documents, isBuilder, onDelete }: Props) {
  return (
    <div role="list" data-testid="vaic-kb-doc-list">
      {documents.map((doc, i) => {
        const meta = fileMeta(doc);
        const metaLine = [
          meta.label,
          formatBytes(doc.size_bytes),
          `${doc.chunk_count} chunk${doc.chunk_count === 1 ? "" : "s"}`,
          `Uploaded ${formatDate(doc.created_at)}`,
        ].join("  ·  ");

        return (
          <div
            key={doc.id}
            role="listitem"
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--color-surface-muted)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-3)",
              padding: "var(--space-3) var(--space-2)",
              borderTop: i === 0 ? "none" : "1px solid var(--color-border)",
              borderRadius: "var(--radius-control, 8px)",
              transition: "background 120ms ease-out",
            }}
          >
            {/* File-type avatar */}
            <div
              aria-hidden="true"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: "40px",
                height: "40px",
                flexShrink: 0,
                borderRadius: "var(--radius-control, 10px)",
                background: meta.bg,
                color: meta.fg,
              }}
            >
              <FileText size={20} strokeWidth={1.75} />
            </div>

            {/* Name + meta */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: "var(--text-body)",
                  fontWeight: 600,
                  color: "var(--color-text-primary)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={doc.filename}
              >
                {doc.filename}
              </div>
              <div
                className="text-caption"
                style={{
                  color: "var(--color-text-tertiary)",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {metaLine}
              </div>
            </div>

            <KbStatusPill status={doc.status} failureReason={doc.failure_reason} />

            {isBuilder && (
              <button
                type="button"
                onClick={() => onDelete(doc.id)}
                aria-label={`Delete ${doc.filename}`}
                title="Delete"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "32px",
                  height: "32px",
                  flexShrink: 0,
                  borderRadius: "var(--radius-control, 8px)",
                  border: "none",
                  background: "transparent",
                  color: "var(--color-text-tertiary)",
                  cursor: "pointer",
                  transition: "background 120ms ease-out, color 120ms ease-out",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "var(--color-surface)";
                  e.currentTarget.style.color = "var(--color-danger, #dc2626)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = "var(--color-text-tertiary)";
                }}
              >
                <Trash2 size={16} strokeWidth={1.5} aria-hidden="true" />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
