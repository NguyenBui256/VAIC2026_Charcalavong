/* Plan 2026-07-18 Task 6 — top-level Tools page (`/tools`): tenant-wide
 * pool of Integrations + Tools, builder-gated authoring. Grant-into-Agent
 * moves to the Agent Builder Tools tab (Task 8); this page owns the pool
 * CRUD only.
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
} from "../../components/ui";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../lib/icons";
import { useIntegrations } from "../../hooks/useIntegrations";
import { useIntegrationMutations } from "../../hooks/useIntegrationMutations";
import { useCatalogTools, useCatalogToolMutations } from "../../hooks/useCatalogTools";
import { useIsBuilder } from "../../hooks/useIsBuilder";
import IntegrationEditor from "../../components/agents/IntegrationEditor";
import ToolEditor from "../../components/agents/ToolEditor";
import ToolTestPanel from "../../components/agents/ToolTestPanel";
import type { ApiIntegration } from "../../lib/integrationsApi";
import type { Tool } from "../../lib/toolsApi";

function truncateUrl(url: string, max = 40): string {
  return url.length > max ? `${url.slice(0, max)}…` : url;
}

export default function ToolsPage() {
  return (
    <div data-testid="vaic-tools-page">
      <header style={{ marginBottom: "var(--space-4)" }}>
        <h1 className="text-h1" style={{ marginBottom: "var(--space-1)" }}>
          Tools
        </h1>
        <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          Tenant-wide catalog of Integrations and Tools. Grant them to individual Agents from
          each Agent's Builder.
        </p>
      </header>

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <IntegrationsSection />
        <ToolsSection />
      </div>
    </div>
  );
}

function IntegrationsSection() {
  const Icon = semanticIcons.ApiIntegration;
  const isBuilder = useIsBuilder();
  const [editingItem, setEditingItem] = useState<ApiIntegration | null | undefined>(undefined);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [testStatus, setTestStatus] = useState<Record<string, "connected" | "disconnected">>({});

  const { query, integrations, isLoading, isError } = useIntegrations();
  const { remove, test } = useIntegrationMutations();
  const { show } = useToast();

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
      onSuccess: (result) => setTestStatus((prev) => ({ ...prev, [integration.id]: result.status })),
      onError: (err) => show(err.message, "error"),
    });
  }

  const columns: TableColumn<ApiIntegration>[] = [
    { key: "name", header: "Name" },
    { key: "base_url", header: "Base URL", render: (i) => truncateUrl(i.base_url) },
    { key: "auth_header_masked", header: "Auth header" },
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
            Test
          </Button>
          {testStatus[i.id] && (
            <span
              className="vaic-pill"
              data-testid={`vaic-integration-status-${i.id}`}
              style={{
                background:
                  testStatus[i.id] === "connected" ? "var(--color-success-soft)" : "var(--color-error-soft)",
                color: testStatus[i.id] === "connected" ? "var(--color-success)" : "var(--color-error)",
              }}
            >
              {testStatus[i.id] === "connected" ? "Connected" : "Disconnected"}
            </span>
          )}
        </div>
      ),
    },
    ...(isBuilder
      ? [
          {
            key: "actions",
            header: "",
            render: (i: ApiIntegration) => (
              <div style={{ display: "flex", gap: "var(--space-2)" }}>
                <Button variant="icon" aria-label={`Edit ${i.name}`} onClick={() => setEditingItem(i)}>
                  <Pencil size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
                </Button>
                <Button variant="icon" aria-label={`Delete ${i.name}`} onClick={() => setPendingDeleteId(i.id)}>
                  <Trash2 size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
                </Button>
              </div>
            ),
          } as TableColumn<ApiIntegration>,
        ]
      : []),
  ];

  function renderBody() {
    if (isError) {
      return (
        <ErrorState
          message={query.error?.message ?? "Failed to load Integrations"}
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
          title="No Integrations yet"
          description={
            isBuilder
              ? "Register a reusable HTTP connection so Tools can call stubbed Gmail, Calendar, or bank-core endpoints."
              : "No API Integrations have been registered in this tenant yet."
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
      title="Integrations"
      headerAction={
        <Icon size={18} strokeWidth={ICON_STROKE_WIDTH} style={{ color: "var(--color-text-tertiary)" }} aria-hidden="true" />
      }
    >
      {editingItem === undefined ? (
        renderBody()
      ) : (
        <IntegrationEditor integration={editingItem} onClose={() => setEditingItem(undefined)} />
      )}

      {isBuilder && editingItem === undefined && (
        <div style={{ marginTop: "var(--space-3)" }}>
          <Button variant="primary" onClick={() => setEditingItem(null)}>
            New Integration
          </Button>
        </div>
      )}

      <ConfirmDialog
        open={pendingDeleteId !== null}
        title="Delete this Integration?"
        body="This removes the Integration registration. Tools referencing it will fail to resolve. This cannot be undone."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={confirmDelete}
        onCancel={() => setPendingDeleteId(null)}
      />
    </Card>
  );
}

function ToolsSection() {
  const Icon = semanticIcons.Tool;
  const isBuilder = useIsBuilder();
  const [editingTool, setEditingTool] = useState<Tool | null | undefined>(undefined);
  const [testingTool, setTestingTool] = useState<Tool | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const { query, tools, isLoading, isError } = useCatalogTools();
  const { remove, test } = useCatalogToolMutations();
  const { integrations } = useIntegrations();
  const { show } = useToast();

  function confirmDelete() {
    if (!pendingDeleteId) return;
    remove.mutate(pendingDeleteId, {
      onSuccess: () => show("Tool deleted"),
      onError: (err) => show(err.message, "error"),
    });
    setPendingDeleteId(null);
  }

  function integrationName(id: string | null): string {
    if (!id) return "—";
    return integrations.find((i) => i.id === id)?.name ?? id;
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
          {t.kind === "builtin" ? "Builtin" : "Integration"}
        </span>
      ),
    },
    { key: "integration_id", header: "Integration", render: (t) => integrationName(t.integration_id) },
    {
      key: "test",
      header: "",
      render: (t) => (
        <Button variant="secondary" onClick={() => setTestingTool(t)} aria-label={`Test ${t.display_name}`}>
          Test
        </Button>
      ),
    },
    ...(isBuilder
      ? [
          {
            key: "actions",
            header: "",
            render: (t: Tool) =>
              t.kind === "integration" ? (
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
              ) : null,
          } as TableColumn<Tool>,
        ]
      : []),
  ];

  function renderBody() {
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
            isBuilder
              ? "Register a Tool backed by an Integration so Agents can take actions beyond text generation."
              : "No Tools have been registered in this tenant yet."
          }
        />
      );
    }
    return <Table<Tool> columns={columns} rows={tools} rowId={(t) => t.id} caption={`${tools.length} tools`} />;
  }

  return (
    <Card
      title="Tools"
      headerAction={
        <Icon size={18} strokeWidth={ICON_STROKE_WIDTH} style={{ color: "var(--color-text-tertiary)" }} aria-hidden="true" />
      }
    >
      {editingTool === undefined ? (
        renderBody()
      ) : (
        <ToolEditor tool={editingTool} onClose={() => setEditingTool(undefined)} />
      )}

      {isBuilder && editingTool === undefined && (
        <div style={{ marginTop: "var(--space-3)" }}>
          <Button variant="primary" onClick={() => setEditingTool(null)}>
            New Tool
          </Button>
        </div>
      )}

      {testingTool && editingTool === undefined && (
        <ToolTestPanel
          isRunning={test.isPending}
          onRun={(sampleInput) => test.mutateAsync({ toolId: testingTool.id, sampleInput })}
        />
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
