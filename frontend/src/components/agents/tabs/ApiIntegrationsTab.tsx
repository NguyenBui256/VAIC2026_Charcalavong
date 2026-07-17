/* Story 2.7 — API Integrations tab: list, New Integration CTA, edit/delete,
 * Test Integration (AC1, AC8, AC9). Replaces the Story 2.2 "Coming soon"
 * placeholder. UX-DR23 branch order (error -> loading -> empty -> data)
 * follows components/dashboard/RecentRuns.tsx and ToolsTab.tsx (Story 2.6).
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
import { useIntegrations } from "../../../hooks/useIntegrations";
import { useIntegrationMutations } from "../../../hooks/useIntegrationMutations";
import { useRegisterTab } from "../AgentBuilderContext";
import IntegrationEditor from "../IntegrationEditor";
import type { ApiIntegration } from "../../../lib/integrationsApi";

export interface ApiIntegrationsTabProps {
  agentId: string;
  isNew: boolean;
}

function truncateUrl(url: string, max = 40): string {
  return url.length > max ? `${url.slice(0, max)}…` : url;
}

export default function ApiIntegrationsTab({ agentId, isNew }: ApiIntegrationsTabProps) {
  const Icon = semanticIcons.ApiIntegration;
  const [editing, setEditing] = useState<ApiIntegration | null | undefined>(undefined);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [testStatus, setTestStatus] = useState<Record<string, "connected" | "disconnected">>({});

  const { query, integrations, isLoading, isError } = useIntegrations(isNew ? undefined : agentId);
  const { remove, test } = useIntegrationMutations(agentId);
  const { show } = useToast();

  // List-style tab — mutations are immediate, never form-buffered (Dev Notes T4.1).
  useRegisterTab("api-integrations", { isDirty: false, save: async () => {}, reset: () => {} });

  function confirmDelete() {
    if (!pendingDeleteId) return;
    remove.mutate(pendingDeleteId, {
      onSuccess: () => show("Integration deleted"),
      onError: (err) => show(err.message, "error"),
    });
    setPendingDeleteId(null);
  }

  function runTest(integration: ApiIntegration) {
    test.mutate(integration.id, {
      onSuccess: (result) =>
        setTestStatus((prev) => ({ ...prev, [integration.id]: result.status })),
      onError: (err) => show(err.message, "error"),
    });
  }

  const columns: TableColumn<ApiIntegration>[] = [
    { key: "name", header: "Name" },
    {
      key: "base_url",
      header: "Base URL",
      render: (i) => truncateUrl(i.base_url),
    },
    {
      key: "last_used_at",
      header: "Last used",
      render: (i) => (i.last_used_at ? new Date(i.last_used_at).toLocaleString() : "Never"),
    },
    {
      key: "test",
      header: "Test",
      render: (i) => (
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <Button
            variant="secondary"
            onClick={() => runTest(i)}
            disabled={test.isPending}
            aria-label={`Test Integration ${i.name}`}
          >
            <Icon size={14} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
            Test Integration
          </Button>
          {testStatus[i.id] && (
            <span
              className="vaic-pill"
              data-testid={`vaic-integration-status-${i.id}`}
              style={{
                background:
                  testStatus[i.id] === "connected"
                    ? "var(--color-success-soft)"
                    : "var(--color-error-soft)",
                color:
                  testStatus[i.id] === "connected"
                    ? "var(--color-success)"
                    : "var(--color-error)",
              }}
            >
              {testStatus[i.id] === "connected" ? "Connected" : "Disconnected"}
            </span>
          )}
        </div>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (i) => (
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button variant="icon" aria-label={`Edit ${i.name}`} onClick={() => setEditing(i)}>
            <Pencil size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
          </Button>
          <Button
            variant="icon"
            aria-label={`Delete ${i.name}`}
            onClick={() => setPendingDeleteId(i.id)}
          >
            <Trash2 size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
          </Button>
        </div>
      ),
    },
  ];

  function renderBody() {
    if (isNew) {
      return (
        <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          Save the Agent first to start registering API Integrations.
        </p>
      );
    }
    if (isError) {
      return (
        <ErrorState
          message={query.error?.message ?? "Failed to load API Integrations"}
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
    if (integrations.length === 0) {
      return (
        <EmptyState
          icon={<Icon size={48} strokeWidth={ICON_STROKE_WIDTH} />}
          title="No API Integrations yet"
          description="Register a reusable HTTP connection so this Agent's Tools can call stubbed Gmail, Calendar, or bank-core endpoints."
          action={
            <Button variant="primary" onClick={() => setEditing(null)}>
              New Integration
            </Button>
          }
        />
      );
    }
    return (
      <Table<ApiIntegration>
        columns={columns}
        rows={integrations}
        rowId={(i) => i.id}
        caption={`${integrations.length} integrations`}
      />
    );
  }

  return (
    <Card
      title="API Integrations"
      headerAction={
        <Icon size={18} strokeWidth={ICON_STROKE_WIDTH} style={{ color: "var(--color-text-tertiary)" }} aria-hidden="true" />
      }
    >
      {!isNew && integrations.length > 0 && editing === undefined && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: "var(--space-3)" }}>
          <Button variant="primary" onClick={() => setEditing(null)}>
            New Integration
          </Button>
        </div>
      )}

      {editing === undefined ? renderBody() : (
        <IntegrationEditor agentId={agentId} integration={editing} onClose={() => setEditing(undefined)} />
      )}

      <ConfirmDialog
        open={pendingDeleteId !== null}
        title="Delete this API Integration?"
        body="This removes the Integration registration. Tools referencing it will fail to resolve. This cannot be undone."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={confirmDelete}
        onCancel={() => setPendingDeleteId(null)}
      />
    </Card>
  );
}
