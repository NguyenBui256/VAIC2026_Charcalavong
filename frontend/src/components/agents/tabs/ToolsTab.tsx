/* Story 2.6 — Tools tab: list, New Tool CTA, edit/delete, Test Tool (AC1, AC6, AC7).
 *
 * Replaces the Story 2.2 "Coming soon" placeholder. UX-DR23 branch order
 * (error -> loading -> empty -> data) follows components/dashboard/RecentRuns.tsx.
 */

import { useState } from "react";
import { Trash2, Pencil } from "lucide-react";
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
import { useAgentTools, useAgentToolMutations } from "../../../hooks/useAgentTools";
import { useRegisterTab } from "../AgentBuilderContext";
import { useEditMode } from "../useEditMode";
import { ListEditActions } from "../TabEditBar";
import ToolEditor from "../ToolEditor";
import type { Tool } from "../../../lib/toolsApi";

export interface ToolsTabProps {
  agentId: string;
  isNew: boolean;
}

export default function ToolsTab({ agentId, isNew }: ToolsTabProps) {
  const Icon = semanticIcons.Tool;
  const [editingTool, setEditingTool] = useState<Tool | null | undefined>(undefined);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const { query, tools, isLoading, isError } = useAgentTools(isNew ? undefined : agentId);
  const { remove } = useAgentToolMutations(agentId);
  const { show } = useToast();
  const { editing, startEdit, stopEdit } = useEditMode(false);

  // List-style tab — mutations are immediate, never form-buffered (Dev Notes T4.1).
  useRegisterTab("tools", { isDirty: false, save: async () => {}, reset: () => {} });

  function confirmDelete() {
    if (!pendingDeleteId) return;
    remove.mutate(pendingDeleteId, {
      onSuccess: () => show("Tool deleted"),
      onError: (err) => show(err.message, "error"),
    });
    setPendingDeleteId(null);
  }

  const columns: TableColumn<Tool>[] = [
    { key: "display_name", header: "Name" },
    {
      key: "kind",
      header: "Kind",
      render: (t) => (
        <span
          className="vaic-pill"
          style={{ background: "var(--color-surface-muted)", color: "var(--color-text-secondary)" }}
        >
          {t.kind === "embedded_python" ? "Embedded Python" : "MCP"}
        </span>
      ),
    },
    {
      key: "updated_at",
      header: "Last modified",
      render: (t) => new Date(t.updated_at).toLocaleString(),
    },
    // Row actions surface only in edit mode — the list is read-only otherwise.
    ...(editing
      ? [
          {
            key: "actions",
            header: "",
            render: (t: Tool) => (
              <div style={{ display: "flex", gap: "var(--space-2)" }}>
                <Button variant="icon" aria-label={`Edit ${t.display_name}`} onClick={() => setEditingTool(t)}>
                  <Pencil size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
                </Button>
                <Button
                  variant="icon"
                  aria-label={`Delete ${t.display_name}`}
                  onClick={() => setPendingDeleteId(t.id)}
                >
                  <Trash2 size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
                </Button>
              </div>
            ),
          } as TableColumn<Tool>,
        ]
      : []),
  ];

  function renderBody() {
    if (isNew) {
      return (
        <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          Save the Agent first to start registering Tools.
        </p>
      );
    }
    if (isError) {
      return (
        <ErrorState
          message={query.error?.message ?? "Failed to load Tools"}
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
    if (tools.length === 0) {
      return (
        <EmptyState
          icon={<Icon size={48} strokeWidth={ICON_STROKE_WIDTH} />}
          title="No Tools yet"
          description={
            editing
              ? "Register a Tool with input/output schemas so this Agent can take actions beyond text generation."
              : "Click Edit to register a Tool with input/output schemas."
          }
        />
      );
    }
    return (
      <Table<Tool> columns={columns} rows={tools} rowId={(t) => t.id} caption={`${tools.length} tools`} />
    );
  }

  return (
    <Card
      title="Tools"
      headerAction={
        <Icon size={18} strokeWidth={ICON_STROKE_WIDTH} style={{ color: "var(--color-text-tertiary)" }} aria-hidden="true" />
      }
    >
      {editingTool === undefined ? renderBody() : (
        <ToolEditor agentId={agentId} tool={editingTool} onClose={() => setEditingTool(undefined)} />
      )}

      {!isNew && editingTool === undefined && (
        <ListEditActions editing={editing} onEdit={startEdit} onDone={stopEdit}>
          {editing && (
            <Button variant="primary" onClick={() => setEditingTool(null)}>
              New Tool
            </Button>
          )}
        </ListEditActions>
      )}

      <ConfirmDialog
        open={pendingDeleteId !== null}
        title="Delete this Tool?"
        body="This removes the Tool registration. This cannot be undone."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={confirmDelete}
        onCancel={() => setPendingDeleteId(null)}
      />
    </Card>
  );
}
