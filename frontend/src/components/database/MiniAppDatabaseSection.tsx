/* Mini-App Databases section (Database page) — list, create/edit schema,
 * read-only rows viewer. Branch order: error -> loading -> empty -> data. */
import { useState, type FormEvent } from "react";
import {
  Button, Card, ConfirmDialog, EmptyState, ErrorState, FormField, Skeleton, Table, useToast,
  type TableColumn,
} from "../ui";
import SchemaFieldEditor from "./SchemaFieldEditor";
import { useMiniAppDatabases, useMiniAppDatabaseMutations, useMiniAppDatabaseRows } from "../../hooks/useMiniAppDatabases";
import type { EntitySchema, MiniAppDatabase, MiniAppDatabaseRow } from "../../lib/miniAppDatabasesApi";

const EMPTY_SCHEMA: EntitySchema = { fields: [{ name: "", type: "string", required: false }] };

interface DraftState {
  id: string | null;         // null = creating
  name: string;
  description: string;
  schema: EntitySchema;
}

export default function MiniAppDatabaseSection() {
  const query = useMiniAppDatabases();
  const { create, update, remove } = useMiniAppDatabaseMutations();
  const { show } = useToast();

  const [draft, setDraft] = useState<DraftState | null>(null);
  const [viewingRowsFor, setViewingRowsFor] = useState<MiniAppDatabase | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const databases = query.data ?? [];

  function startCreate() {
    setDraft({ id: null, name: "", description: "", schema: EMPTY_SCHEMA });
  }
  function startEdit(db: MiniAppDatabase) {
    setDraft({ id: db.id, name: db.name, description: db.description, schema: db.entity_schema });
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!draft) return;
    if (!draft.name.trim()) { show("Name is required", "error"); return; }
    if (draft.schema.fields.length === 0 || draft.schema.fields.some((f) => !f.name.trim())) {
      show("Every field needs a name", "error"); return;
    }
    const input = { name: draft.name, description: draft.description, entity_schema: draft.schema };
    if (draft.id === null) {
      create.mutate(input, {
        onSuccess: () => { show("Database created"); setDraft(null); },
        onError: (err) => show(err.message || "Failed to create database", "error"),
      });
    } else {
      update.mutate({ id: draft.id, input }, {
        onSuccess: () => { show("Database updated"); setDraft(null); },
        onError: (err) => show(err.message || "Failed to update database", "error"),
      });
    }
  }

  function confirmDelete() {
    if (!pendingDeleteId) return;
    remove.mutate(pendingDeleteId, {
      onSuccess: () => show("Database deleted"),
      onError: (err) => show(err.message, "error"),
    });
    setPendingDeleteId(null);
  }

  const columns: TableColumn<MiniAppDatabase>[] = [
    { key: "name", header: "Name" },
    { key: "description", header: "Description", render: (d) => d.description || "—" },
    { key: "fields", header: "Fields", render: (d) => String(d.entity_schema.fields.length) },
    {
      key: "actions", header: "",
      render: (d) => (
        <div style={{ display: "flex", gap: "var(--space-1)" }}>
          <Button variant="secondary" onClick={() => setViewingRowsFor(d)}>Data</Button>
          <Button variant="secondary" onClick={() => startEdit(d)}>Edit</Button>
          <Button variant="secondary" onClick={() => setPendingDeleteId(d.id)}>Delete</Button>
        </div>
      ),
    },
  ];

  function renderList() {
    if (query.isError) {
      return (
        <ErrorState
          message={query.error?.message ?? "Failed to load databases"}
          retry={<Button variant="secondary" onClick={() => query.refetch()}>Retry</Button>}
        />
      );
    }
    if (query.isLoading) return <Skeleton lines={3} height="24px" />;
    if (databases.length === 0) {
      return <EmptyState title="No databases yet" description="Create a database to define a reusable schema for Mini-Apps." />;
    }
    return <Table<MiniAppDatabase> columns={columns} rows={databases} rowId={(d) => d.id} caption="Mini-App Databases" />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card
        title="Mini-App Databases"
        headerAction={<Button variant="primary" onClick={startCreate}>New database</Button>}
      >
        {renderList()}
      </Card>

      {draft && (
        <Card title={draft.id === null ? "Create database" : "Edit database"}>
          <form onSubmit={handleSubmit}>
            <FormField
              label="Name" required value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
            <div className="vaic-form-field">
              <label className="vaic-form-label" htmlFor="vaic-db-description">Description</label>
              <textarea
                id="vaic-db-description" rows={2} className="vaic-form-input vaic-focusable"
                value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              />
            </div>
            <div className="vaic-form-field">
              <label className="vaic-form-label">Schema fields</label>
              <SchemaFieldEditor value={draft.schema} onChange={(schema) => setDraft({ ...draft, schema })} />
            </div>
            <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-3)" }}>
              <Button variant="primary" type="submit" disabled={create.isPending || update.isPending}>
                {draft.id === null ? "Create" : "Save"}
              </Button>
              <Button variant="secondary" type="button" onClick={() => setDraft(null)}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {viewingRowsFor && (
        <DatabaseRowsCard db={viewingRowsFor} onClose={() => setViewingRowsFor(null)} />
      )}

      <ConfirmDialog
        open={pendingDeleteId !== null}
        title="Delete this database?"
        body="Mini-Apps referencing it keep their copied schema but lose the link. This cannot be undone."
        confirmLabel="Delete" cancelLabel="Cancel"
        onConfirm={confirmDelete} onCancel={() => setPendingDeleteId(null)}
      />
    </div>
  );
}

function DatabaseRowsCard({ db, onClose }: { db: MiniAppDatabase; onClose: () => void }) {
  const rowsQuery = useMiniAppDatabaseRows(db.id);
  const rows = rowsQuery.data ?? [];
  const fieldNames = db.entity_schema.fields.map((f) => f.name);

  const columns: TableColumn<MiniAppDatabaseRow>[] = fieldNames.map((name) => ({
    key: name, header: name,
    render: (r) => {
      const v = r.data[name];
      return v === undefined || v === null ? "—" : String(v);
    },
  }));

  return (
    <Card title={`Data — ${db.name}`} headerAction={<Button variant="secondary" onClick={onClose}>Close</Button>}>
      {rowsQuery.isError ? (
        <ErrorState
          message={rowsQuery.error?.message ?? "Failed to load rows"}
          retry={<Button variant="secondary" onClick={() => rowsQuery.refetch()}>Retry</Button>}
        />
      ) : rowsQuery.isLoading ? (
        <Skeleton lines={3} height="20px" />
      ) : rows.length === 0 ? (
        <EmptyState title="No data yet" description="Mini-Apps using this database will show their records here." />
      ) : (
        <Table<MiniAppDatabaseRow> columns={columns} rows={rows} rowId={(r) => r.row_id} caption={`${db.name} rows`} />
      )}
    </Card>
  );
}
