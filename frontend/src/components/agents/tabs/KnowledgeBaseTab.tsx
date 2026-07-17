/* Story 2.4 — Knowledge Base tab: upload, status-aware list, delete.
 *
 * Replaces the Story 2.2 "Coming soon" placeholder. UX-DR23 branch order
 * (error -> loading -> empty -> data) follows components/dashboard/RecentRuns.tsx.
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
} from "../../ui";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../../lib/icons";
import { useKbDocuments } from "../../../hooks/useKbDocuments";
import { useKbMutations } from "../../../hooks/useKbMutations";
import KbStatusPill from "../KbStatusPill";
import {
  KB_MAX_BYTES,
  KB_ACCEPTED_EXTENSIONS,
  KB_ACCEPTED_MIME_TYPES,
  type KbDocument,
} from "../../../lib/kbApi";

export interface KnowledgeBaseTabProps {
  agentId: string;
  isNew: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function hasAcceptedExtension(filename: string): boolean {
  const lower = filename.toLowerCase();
  return KB_ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

/** AC3 — client-side 20MB + type gate. Returns an error message, or null. */
function validateFile(file: File): string | null {
  if (file.size > KB_MAX_BYTES) {
    return `"${file.name}" exceeds the 20MB limit`;
  }
  if (!KB_ACCEPTED_MIME_TYPES.has(file.type) && !hasAcceptedExtension(file.name)) {
    return `"${file.name}" is not a supported file type (PDF, TXT, Markdown, DOCX only)`;
  }
  return null;
}

export default function KnowledgeBaseTab({ agentId, isNew }: KnowledgeBaseTabProps) {
  const Icon = semanticIcons.KnowledgeBase;
  const inputRef = useRef<HTMLInputElement>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const { query, documents, isLoading, isError } = useKbDocuments(isNew ? undefined : agentId);
  const { upload, remove } = useKbMutations(agentId);
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
    {
      key: "actions",
      header: "",
      render: (d) => (
        <Button
          variant="icon"
          aria-label={`Delete ${d.filename}`}
          onClick={() => setPendingDeleteId(d.id)}
        >
          <Trash2 size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
        </Button>
      ),
    },
  ];

  function renderBody() {
    if (isNew) {
      return (
        <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          Save the Agent first to start uploading Knowledge Base documents.
        </p>
      );
    }
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
          description="Upload policy, regulation, or SOP documents to ground this Agent's responses."
          action={
            <Button variant="primary" onClick={() => inputRef.current?.click()}>
              Upload document
            </Button>
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
    <Card
      title="Knowledge Base"
      headerAction={
        <Icon
          size={18}
          strokeWidth={ICON_STROKE_WIDTH}
          style={{ color: "var(--color-text-tertiary)" }}
          aria-hidden="true"
        />
      }
    >
      <div
        className="vaic-inline-alert vaic-inline-alert-warning"
        role="note"
        data-testid="vaic-kb-nfr9-advisory"
        style={{ marginBottom: "var(--space-3)" }}
      >
        Policy / regulation / SOP documents only. Do not upload documents containing
        real customer PII.
      </div>

      {!isNew && documents.length > 0 && (
        <div
          style={{
            display: "flex",
            justifyContent: "flex-end",
            marginBottom: "var(--space-3)",
          }}
        >
          <Button
            variant="primary"
            onClick={() => inputRef.current?.click()}
            disabled={upload.isPending}
          >
            Upload document
          </Button>
        </div>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={KB_ACCEPTED_EXTENSIONS.join(",")}
        style={{ display: "none" }}
        onChange={handleInputChange}
        data-testid="vaic-kb-file-input"
      />

      {renderBody()}

      <ConfirmDialog
        open={pendingDeleteId !== null}
        title="Delete this document?"
        body="This removes the document and all its indexed chunks/embeddings. This cannot be undone."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={confirmDelete}
        onCancel={() => setPendingDeleteId(null)}
      />
    </Card>
  );
}
