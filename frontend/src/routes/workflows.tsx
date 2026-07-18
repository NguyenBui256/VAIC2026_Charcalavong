/* Story 3.1 — Workflow list surface (/workflows), AC #5. */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Table, EmptyState, ErrorState, Skeleton } from "../components/ui";
import type { TableColumn } from "../components/ui";
import { useWorkflows } from "../hooks/useWorkflows";
import { useDebounce } from "../lib/useDebounce";
import { semanticIcons, ICON_STROKE_WIDTH } from "../lib/icons";
import type { Workflow } from "../lib/workflowsApi";
import NewWorkflowModal from "../components/workflows/NewWorkflowModal";
import type { CreateSeed } from "../lib/graphTemplates";

export default function WorkflowsPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [newOpen, setNewOpen] = useState(false);
  const debouncedSearch = useDebounce(search, 200);

  const { query, data: workflows, isLoading, isError } = useWorkflows({
    search: debouncedSearch || undefined,
    owner_id: ownerId || undefined,
  });

  const rows = workflows ?? [];
  const isEmpty = !isLoading && !isError && rows.length === 0;
  const WorkflowIcon = semanticIcons.Orchestrator;

  // Story 3.1 scope: no run_count/last-run columns yet (workflow_runs is
  // Story 3.2's table — a computed join belongs in Story 3.7's Runs list,
  // not stored/faked here, YAGNI). Name/owner satisfy AC5's required
  // columns for this story; status pill + run stats arrive with Story 3.7.
  const columns: TableColumn<Workflow>[] = [
    { key: "name", header: "Name" },
    { key: "owner_id", header: "Owner" },
    {
      key: "updated_at",
      header: "Last modified",
      render: (row) => new Date(row.updated_at).toLocaleString(),
    },
  ];

  function handleNewConfirm(seed: CreateSeed) {
    setNewOpen(false);
    navigate("/workflows/new", { state: { seed } });
  }

  function renderBody() {
    if (isError) {
      return (
        <ErrorState
          message={query.error?.message ?? "Failed to load Workflows"}
          retry={
            <Button variant="secondary" onClick={() => query.refetch()}>
              Retry
            </Button>
          }
        />
      );
    }
    if (isLoading) {
      return (
        <div
          data-testid="vaic-workflows-loading"
          style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}
        >
          <Skeleton height="40px" />
          <Skeleton height="40px" />
          <Skeleton height="40px" />
        </div>
      );
    }
    return (
      <Table
        columns={columns}
        rows={rows}
        rowId={(row) => row.id}
        onRowClick={(row) => navigate(`/workflows/${row.id}`)}
        emptyState={
          <EmptyState
            icon={<WorkflowIcon size={48} strokeWidth={ICON_STROKE_WIDTH} />}
            title="No workflows yet."
            description="Create your first Workflow to get started."
            action={
              <Button variant="primary" onClick={() => setNewOpen(true)}>
                New Workflow
              </Button>
            }
          />
        }
      />
    );
  }

  return (
    <div data-testid="vaic-workflows-page">
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
            Workflows
          </h1>
          <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
            Every Workflow in your Tenant, searchable and filterable by owner.
          </p>
        </div>
        {!isEmpty && (
          <Button variant="primary" onClick={() => setNewOpen(true)}>
            New Workflow
          </Button>
        )}
      </header>

      <div className="vaic-workflows-filters">
        <input
          type="search"
          aria-label="Search Workflows"
          placeholder="Search by name"
          className="vaic-form-input vaic-focusable"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <input
          type="text"
          aria-label="Filter by Owner"
          placeholder="Filter by owner id"
          className="vaic-form-input vaic-focusable"
          value={ownerId}
          onChange={(e) => setOwnerId(e.target.value)}
        />
      </div>

      {renderBody()}

      <NewWorkflowModal
        open={newOpen}
        onCancel={() => setNewOpen(false)}
        onConfirm={handleNewConfirm}
      />
    </div>
  );
}
