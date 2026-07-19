/* Story 2.2 — Agent list surface (/agents), AC #1-4. */

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Table, EmptyState, ErrorState, Skeleton } from "../components/ui";
import type { TableColumn } from "../components/ui";
import AgentStatusPill from "../components/agents/AgentStatusPill";
import DepartmentBadge from "../components/agents/DepartmentBadge";
import { useAgents } from "../hooks/useAgents";
import { useDepartments } from "../hooks/useDepartments";
import { useDebounce } from "../lib/useDebounce";
import { semanticIcons, ICON_STROKE_WIDTH } from "../lib/icons";
import type { Agent } from "../lib/agentsApi";

export default function AgentsPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const debouncedSearch = useDebounce(search, 200);

  const { data: departments } = useDepartments();
  const { query, data: agents, isLoading, isError } = useAgents({
    department_id: departmentId || undefined,
    q: debouncedSearch || undefined,
  });

  const deptNameById = useMemo(() => {
    const map = new Map<string, string>();
    (departments ?? []).forEach((d) => map.set(d.id, d.name));
    return map;
  }, [departments]);

  const rows = agents ?? [];
  const isEmpty = !isLoading && !isError && rows.length === 0;
  const AgentIcon = semanticIcons.Agent;

  const columns: TableColumn<Agent>[] = [
    { key: "name", header: "Name" },
    {
      key: "department",
      header: "Department",
      render: (row) => (
        <DepartmentBadge name={deptNameById.get(row.department_id) ?? row.department_id} />
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (row) => <AgentStatusPill status={row.status} />,
    },
    { key: "owner_id", header: "Owner" },
    {
      key: "updated_at",
      header: "Last modified",
      render: (row) => new Date(row.updated_at).toLocaleString(),
    },
  ];

  function renderBody() {
    if (isError) {
      return (
        <ErrorState
          message={query.error?.message ?? "Failed to load Agents"}
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
          data-testid="vaic-agents-loading"
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
        onRowClick={(row) => navigate(`/agents/${row.id}`)}
        emptyState={
          <EmptyState
            icon={<AgentIcon size={48} strokeWidth={ICON_STROKE_WIDTH} />}
            title="No Agents yet"
            description="Create your first Agent to get started."
            action={
              <Button variant="primary" onClick={() => navigate("/agents/new")}>
                New Agent
              </Button>
            }
          />
        }
      />
    );
  }

  return (
    <div data-testid="vaic-agents-page">
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
            Agents
          </h1>
          <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
            Every Agent in your Tenant, searchable and filterable by Department.
          </p>
        </div>
        {!isEmpty && (
          <Button variant="primary" onClick={() => navigate("/agents/new")}>
            New Agent
          </Button>
        )}
      </header>

      <div className="vaic-agents-filters">
        <select
          aria-label="Filter by Department"
          className="vaic-form-input vaic-focusable"
          value={departmentId}
          onChange={(e) => setDepartmentId(e.target.value)}
        >
          <option value="">All Departments</option>
          {(departments ?? []).map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <input
          type="search"
          aria-label="Search Agents"
          placeholder="Search by name"
          className="vaic-form-input vaic-focusable"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {renderBody()}
    </div>
  );
}
