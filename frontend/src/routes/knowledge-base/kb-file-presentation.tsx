/* Presentation helpers for Knowledge Base documents — friendly type labels and
 * per-type file icons. Keeps KnowledgeBasePage focused on data/state wiring.
 *
 * Type resolution mirrors the client-side gate in kbApi.ts (extension + MIME),
 * so the label stays correct even when the browser reports a generic MIME. */

import type { ReactNode } from "react";
import { FileText, FileCode, FileType, File } from "lucide-react";
import { ICON_STROKE_WIDTH } from "../../lib/icons";
import type { KbDocument } from "../../lib/kbApi";

type FileKind = "pdf" | "word" | "markdown" | "text" | "other";

/** Resolve a document to a coarse file kind from extension first, MIME second. */
function resolveKind(doc: Pick<KbDocument, "filename" | "content_type">): FileKind {
  const name = doc.filename.toLowerCase();
  if (name.endsWith(".pdf") || doc.content_type === "application/pdf") return "pdf";
  if (name.endsWith(".docx") || doc.content_type.includes("wordprocessingml")) return "word";
  if (name.endsWith(".md") || name.endsWith(".markdown") || doc.content_type.includes("markdown"))
    return "markdown";
  if (name.endsWith(".txt") || doc.content_type === "text/plain") return "text";
  return "other";
}

const KIND_LABEL: Record<FileKind, string> = {
  pdf: "PDF",
  word: "Word",
  markdown: "Markdown",
  text: "Text",
  other: "File",
};

/** Each kind maps to a lucide icon + a semantic token color. */
const KIND_ICON: Record<FileKind, { Icon: typeof FileText; color: string }> = {
  pdf: { Icon: FileText, color: "var(--color-destructive)" },
  word: { Icon: FileType, color: "var(--color-running)" },
  markdown: { Icon: FileCode, color: "var(--color-primary)" },
  text: { Icon: FileText, color: "var(--color-text-tertiary)" },
  other: { Icon: File, color: "var(--color-text-tertiary)" },
};

/** Human-readable type label, e.g. "application/pdf" -> "PDF". */
export function friendlyType(doc: Pick<KbDocument, "filename" | "content_type">): string {
  return KIND_LABEL[resolveKind(doc)];
}

/** Byte count -> compact human string (B / KB / MB). Shared by page + stats. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Ingest progress indicator for a `processing` document. Shows the real % of
 * chunks embedded (from the RAG store). While the percent is still unknown —
 * the extract/OCR phase before chunk count is known — it falls back to an
 * indeterminate sweep so the bar still reads as "working".
 */
export function KbProcessingIndicator({ progress }: { progress?: number }): ReactNode {
  const hasPercent = typeof progress === "number" && progress > 0;
  const pct = hasPercent ? Math.min(100, Math.max(0, Math.round(progress))) : 0;
  return (
    <span
      style={{
        display: "inline-flex",
        flexDirection: "column",
        gap: "4px",
        minWidth: "110px",
      }}
    >
      <span
        className="vaic-progress"
        role="progressbar"
        aria-label="Processing document"
        aria-valuenow={hasPercent ? pct : undefined}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        {hasPercent ? (
          <span className="vaic-progress-bar is-determinate" style={{ width: `${pct}%` }} />
        ) : (
          <span className="vaic-progress-bar" />
        )}
      </span>
      <span
        style={{
          fontSize: "11px",
          color: "var(--color-text-tertiary)",
          textAlign: "center",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {hasPercent ? `${pct}%` : "…"}
      </span>
    </span>
  );
}

/** Filename cell: colored file-type icon + name (medium weight, truncating). */
export function FileNameCell({ doc }: { doc: KbDocument }): ReactNode {
  const { Icon, color } = KIND_ICON[resolveKind(doc)];
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-2)", minWidth: 0 }}>
      <Icon size={16} strokeWidth={ICON_STROKE_WIDTH} color={color} aria-hidden="true" style={{ flexShrink: 0 }} />
      <span
        style={{
          fontWeight: 500,
          color: "var(--color-text)",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          maxWidth: "34ch",
        }}
        title={doc.filename}
      >
        {doc.filename}
      </span>
    </span>
  );
}
