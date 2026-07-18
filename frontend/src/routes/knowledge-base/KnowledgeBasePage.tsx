/* Plan 2026-07-18 Task 7 — top-level Knowledge Base page (`/knowledge-base`):
 * tenant-wide document pool, builder-gated upload/delete. Grant-into-Agent
 * moves to the Agent Builder Knowledge Base tab (Task 8); this page owns
 * the pool CRUD only. Status polling handled by `useKbPool`.
 */

import { useRef, useState, type ChangeEvent } from "react";
import { Trash2 } from "lucide-react";
import {
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Skeleton,
  Table,
  useToast,
  type TableColumn,
} from "../../components/ui";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../lib/icons";
import { useKbPool, useKbPoolMutations } from "../../hooks/useKbPool";
import { useIsBuilder } from "../../hooks/useIsBuilder";
import KbStatusPill from "../../components/agents/KbStatusPill";
import {
  KB_MAX_BYTES,
  KB_ACCEPTED_EXTENSIONS,
  KB_ACCEPTED_MIME_TYPES,
  type KbDocument,
} from "../../lib/kbApi";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function hasAcceptedExtension(filename: string): boolean {
  const lower = filename.toLowerCase();
  return KB_ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

/** Client-side 20MB + type gate (mirrors KnowledgeBaseTab.tsx). */
function validateFile(file: File): string | null {
  if (file.size > KB_MAX_BYTES) {
    return `"${file.name}" exceeds the 20MB limit`;
  }
  if (!KB_ACCEPTED_MIME_TYPES.has(file.type) && !hasAcceptedExtension(file.name)) {
    return `"${file.name}" is not a supported file type (PDF, TXT, Markdown, DOCX only)`;
  }
  return null;
}

export default function KnowledgeBasePage() {
  const Icon = semanticIcons.KnowledgeBase;
  const isBuilder = useIsBuilder();
  const inputRef = useRef<HTMLInputElement>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const { query, documents, isLoading, isError } = useKbPool();
  const { upload, remove } = useKbPoolMutations();
  const { show } = useToast();

  function handleFileSelected(file: File) {
    const error = validateFile(file);
    if (error) {
      show(error, "error");
      return;
    }
    upload.mutate(file, {
      onSuccess: () => show(`"${file.name}" uploaded`),
      onError: (err) => show(err.message, "error"),
    });
  }

  function handleInputChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) handleFileSelected(file);
  }

  function confirmDelete() {
    if (!pendingDeleteId) return;
    remove.mutate(pendingDeleteId, {
      onSuccess: () => show("Document deleted"),
      onError: (err) => show(err.message, "error"),
    });
    setPendingDeleteId(null);
  }

  const columns: TableColumn<KbDocument>[] = [
    { key: "filename", header: "Name" },
    { key: "content_type", header: "Type" },
    { key: "size_bytes", header: "Size", render: (d) => formatBytes(d.size_bytes) },
    { key: "chunk_count", header: "Chunks" },
    {
      key: "status",
      header: "Status",
      render: (d) => <KbStatusPill status={d.status} failureReason={d.failure_reason} />,
    },
    {
      key: "created_at",
      header: "Uploaded",
      render: (d) => new Date(d.created_at).toLocaleString(),
    },
    ...(isBuilder
      ? [
          {
            key: "actions",
            header: "",
            render: (d: KbDocument) => (
              <Button
                variant="icon"
                aria-label={`Delete ${d.filename}`}
                onClick={() => setPendingDeleteId(d.id)}
              >
                <Trash2 size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
              </Button>
            ),
          } as TableColumn<KbDocument>,
        ]
      : []),
  ];

  function renderBody() {
    if (isError) {
      return (
        <ErrorState
          message={query.error?.message ?? "Failed to load Knowledge Base"}
          retry={
            <Button variant="secondary" onClick={() => query.refetch()}>
              Retry
            </Button>
          }
        />
      );
    }
    if (isLoading) {
      return <Skeleton lines={4} height="20px" />;
    }
    if (documents.length === 0) {
      return (
        <EmptyState
          icon={<Icon size={48} strokeWidth={ICON_STROKE_WIDTH} />}
          title="No documents yet"
          description={
            isBuilder
              ? "Upload policy, regulation, or SOP documents to ground Agents' responses."
              : "No Knowledge Base documents have been uploaded in this tenant yet."
          }
          action={
            isBuilder ? (
              <Button variant="primary" onClick={() => inputRef.current?.click()} disabled={upload.isPending}>
                Upload document
              </Button>
            ) : undefined
          }
        />
      );
    }
    return (
      <Table<KbDocument>
        columns={columns}
        rows={documents}
        rowId={(d) => d.id}
        caption="Knowledge Base documents"
      />
    );
  }

  return (
    <div data-testid="vaic-knowledge-base-page">
      <header
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: "var(--space-3)",
          marginBottom: "var(--space-4)",
        }}
      >
        <div>
          <h1 className="text-h1" style={{ marginBottom: "var(--space-1)" }}>
            Knowledge Base
          </h1>
          <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
            Tenant-wide document pool. Grant documents to individual Agents from each Agent's
            Builder.
          </p>
        </div>
        {isBuilder && documents.length > 0 && (
          <Button variant="primary" onClick={() => inputRef.current?.click()} disabled={upload.isPending}>
            Upload document
          </Button>
        )}
      </header>

      <div
        className="vaic-inline-alert vaic-inline-alert-warning"
        role="note"
        data-testid="vaic-kb-nfr9-advisory"
        style={{ marginBottom: "var(--space-3)" }}
      >
        Policy / regulation / SOP documents only. Do not upload documents containing real
        customer PII.
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={KB_ACCEPTED_EXTENSIONS.join(",")}
        style={{ display: "none" }}
        onChange={handleInputChange}
        data-testid="vaic-kb-file-input"
      />

      <Card>{renderBody()}</Card>

      <ConfirmDialog
        open={pendingDeleteId !== null}
        title="Delete this document?"
        body="This removes the document and all its indexed chunks/embeddings. This cannot be undone."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={confirmDelete}
        onCancel={() => setPendingDeleteId(null)}
      />
    </div>
  );
}
