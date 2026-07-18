/* Plan 2026-07-18 Task 8 — Knowledge Base tab as a grant picker.
 *
 * Upload/delete moved to the tenant-level `/knowledge-base` page (Task 7).
 * This tab only lets a Builder attach/detach pool documents to THIS agent
 * (checkbox = granted). Read-only for non-builders.
 */

import { Link } from "react-router-dom";
import { Button, Card, EmptyState, ErrorState, Skeleton, Table, useToast, type TableColumn } from "../../ui";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../../lib/icons";
import { useKbPool } from "../../../hooks/useKbPool";
import { useAgentGrants } from "../../../hooks/useAgentGrants";
import { useIsBuilder } from "../../../hooks/useIsBuilder";
import { useRegisterTab } from "../AgentBuilderContext";
import KbStatusPill from "../KbStatusPill";
import type { KbDocument } from "../../../lib/kbApi";

export interface KnowledgeBaseTabProps {
  agentId: string;
  isNew: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function KnowledgeBaseTab({ agentId, isNew }: KnowledgeBaseTabProps) {
  const Icon = semanticIcons.KnowledgeBase;
  const isBuilder = useIsBuilder();
  const { query, documents, isLoading, isError } = useKbPool();
  const { kb: grantedKb, attachKb, detachKb } = useAgentGrants(isNew ? undefined : agentId);
  const { show } = useToast();

  // Grant toggles are immediate mutations — never form-buffered (Dev Notes T4.1).
  useRegisterTab("knowledge-base", { isDirty: false, save: async () => {}, reset: () => {} });

  const grantedIds = new Set(grantedKb.map((d) => d.id));

  function toggle(doc: KbDocument) {
    if (!isBuilder) return;
    if (grantedIds.has(doc.id)) {
      detachKb.mutate(doc.id, { onError: (err) => show(err.message, "error") });
    } else {
      attachKb.mutate(doc.id, { onError: (err) => show(err.message, "error") });
    }
  }

  const columns: TableColumn<KbDocument>[] = [
    {
      key: "granted",
      header: "",
      render: (d) => (
        <input
          type="checkbox"
          checked={grantedIds.has(d.id)}
          disabled={!isBuilder || attachKb.isPending || detachKb.isPending}
          aria-label={`Grant ${d.filename} to this agent`}
          onChange={() => toggle(d)}
        />
      ),
    },
    { key: "filename", header: "Name" },
    { key: "content_type", header: "Type" },
    { key: "size_bytes", header: "Size", render: (d) => formatBytes(d.size_bytes) },
    {
      key: "status",
      header: "Status",
      render: (d) => <KbStatusPill status={d.status} failureReason={d.failure_reason} />,
    },
  ];

  function renderBody() {
    if (isNew) {
      return (
        <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          Save the Agent first to start granting Knowledge Base documents.
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
          title="No documents in the catalog yet"
          description="Upload documents from the Knowledge Base page, then grant them to this Agent here."
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
      {renderBody()}

      {!isNew && (
        <div style={{ marginTop: "var(--space-3)" }}>
          <Link to="/knowledge-base" className="text-body" style={{ color: "var(--color-accent)" }}>
            Manage KB
          </Link>
        </div>
      )}
    </Card>
  );
}
