/* Plan 2026-07-18 Task 8 — Tools tab as a grant picker.
 *
 * Pool authoring (create/edit/delete/test) moved to the tenant-level
 * `/tools` page (Task 6). This tab only lets a Builder attach/detach pool
 * Tools to THIS agent (checkbox = granted). Read-only for non-builders.
 */

import { Link } from "react-router-dom";
import { Button, Card, EmptyState, ErrorState, Skeleton, Table, useToast, type TableColumn } from "../../ui";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../../lib/icons";
import { useCatalogTools } from "../../../hooks/useCatalogTools";
import { useAgentGrants } from "../../../hooks/useAgentGrants";
import { useIsBuilder } from "../../../hooks/useIsBuilder";
import { useRegisterTab } from "../AgentBuilderContext";
import type { Tool } from "../../../lib/toolsApi";

export interface ToolsTabProps {
  agentId: string;
  isNew: boolean;
}

export default function ToolsTab({ agentId, isNew }: ToolsTabProps) {
  const Icon = semanticIcons.Tool;
  const isBuilder = useIsBuilder();
  const { query, tools, isLoading, isError } = useCatalogTools();
  const { tools: grantedTools, attachTool, detachTool } = useAgentGrants(isNew ? undefined : agentId);
  const { show } = useToast();

  // Grant toggles are immediate mutations — never form-buffered (Dev Notes T4.1).
  useRegisterTab("tools", { isDirty: false, save: async () => {}, reset: () => {} });

  const grantedIds = new Set(grantedTools.map((t) => t.id));

  function toggle(tool: Tool) {
    if (!isBuilder) return;
    if (grantedIds.has(tool.id)) {
      detachTool.mutate(tool.id, { onError: (err) => show(err.message, "error") });
    } else {
      attachTool.mutate(tool.id, { onError: (err) => show(err.message, "error") });
    }
  }

  const columns: TableColumn<Tool>[] = [
    {
      key: "granted",
      header: "",
      render: (t) => (
        <input
          type="checkbox"
          checked={grantedIds.has(t.id)}
          disabled={!isBuilder || attachTool.isPending || detachTool.isPending}
          aria-label={`Grant ${t.display_name} to this agent`}
          onChange={() => toggle(t)}
        />
      ),
    },
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
  ];

  function renderBody() {
    if (isNew) {
      return (
        <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
          Save the Agent first to start granting Tools.
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
          title="No Tools in the catalog yet"
          description="Register Tools from the Tools page, then grant them to this Agent here."
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
      {renderBody()}

      {!isNew && (
        <div style={{ marginTop: "var(--space-3)" }}>
          <Link to="/tools" className="text-body" style={{ color: "var(--color-accent)" }}>
            Manage tools
          </Link>
        </div>
      )}
    </Card>
  );
}
