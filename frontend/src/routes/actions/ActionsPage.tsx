/* Actions page — bind a Mini-App Database row event to a Workflow. List +
 * create/edit + delete. Branch order: error -> loading -> empty -> data.
 *
 * Note: `FormField` always overrides its internal input's `onChange` with its
 * own `handleChange` (see components/ui/FormField.tsx) — a caller-supplied
 * `onChange` prop is silently dropped, so a controlled `value`/`onChange`
 * pair passed straight to `FormField` never reaches parent state. We use the
 * `children` slot with a raw `<input>` instead (same pattern as the native
 * `<select>` fields below) for the "Name" and "Notify user IDs" fields.
 */
import { useState, type FormEvent } from "react";
import {
  Button, Card, ConfirmDialog, EmptyState, ErrorState, FormField, Skeleton, Table, useToast,
  type TableColumn,
} from "../../components/ui";
import { useActions, useActionMutations, useMiniAppDatabasesList } from "../../hooks/useActions";
import { useWorkflows } from "../../hooks/useWorkflows";
import { useAgents } from "../../hooks/useAgents";
import type { ActionBinding, ActionEventType, ActionTargetType, CreateActionInput } from "../../lib/actionsApi";

const EVENT_TYPES: ActionEventType[] = ["row.created", "row.updated", "row.deleted"];

interface DraftState {
  id: string | null;
  name: string;
  database_id: string;
  event_type: ActionEventType;
  target_type: ActionTargetType;
  workflow_id: string;
  agent_id: string;
  notify_user_ids: string; // comma-separated in the form
  is_active: boolean;
}

const EMPTY_DRAFT: DraftState = {
  id: null, name: "", database_id: "", event_type: "row.created",
  target_type: "workflow", workflow_id: "", agent_id: "",
  notify_user_ids: "", is_active: true,
};

export default function ActionsPage() {
  const query = useActions();
  const dbQuery = useMiniAppDatabasesList();
  const { data: workflowsData } = useWorkflows({});
  const { data: agentsData } = useAgents({});
  const { create, update, remove } = useActionMutations();
  const { show } = useToast();

  const [draft, setDraft] = useState<DraftState | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const actions = query.data ?? [];
  const databases = dbQuery.data ?? [];
  const workflows = workflowsData ?? [];
  const dbName = (id: string) => databases.find((d) => d.id === id)?.name ?? id;
  const wfName = (id: string) => workflows.find((w) => w.id === id)?.name ?? id;
  const agents = agentsData ?? [];
  const agName = (id: string) => agents.find((a) => a.id === id)?.name ?? id;

  function startCreate() { setDraft({ ...EMPTY_DRAFT }); }
  function startEdit(a: ActionBinding) {
    setDraft({
      id: a.id, name: a.name, database_id: a.database_id, event_type: a.event_type,
      target_type: a.target_type,
      workflow_id: a.workflow_id ?? "", agent_id: a.agent_id ?? "",
      notify_user_ids: a.notify_user_ids.join(", "), is_active: a.is_active,
    });
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!draft) return;
    if (!draft.name.trim()) { show("Name is required", "error"); return; }
    if (!draft.database_id) { show("Pick a Mini-App Database", "error"); return; }
    if (draft.target_type === "workflow" && !draft.workflow_id) { show("Pick a Workflow", "error"); return; }
    if (draft.target_type === "agent" && !draft.agent_id) { show("Pick an Agent", "error"); return; }
    const input: CreateActionInput = {
      name: draft.name.trim(),
      database_id: draft.database_id,
      event_type: draft.event_type,
      target_type: draft.target_type,
      workflow_id: draft.target_type === "workflow" ? draft.workflow_id : null,
      agent_id: draft.target_type === "agent" ? draft.agent_id : null,
      notify_user_ids: draft.notify_user_ids.split(",").map((s) => s.trim()).filter(Boolean),
      is_active: draft.is_active,
    };
    if (draft.id === null) {
      create.mutate(input, {
        onSuccess: () => { show("Action created"); setDraft(null); },
        onError: (err) => show(err.message || "Failed to create action", "error"),
      });
    } else {
      update.mutate({ id: draft.id, input }, {
        onSuccess: () => { show("Action updated"); setDraft(null); },
        onError: (err) => show(err.message || "Failed to update action", "error"),
      });
    }
  }

  function confirmDelete() {
    if (!pendingDeleteId) return;
    remove.mutate(pendingDeleteId, {
      onSuccess: () => show("Action deleted"),
      onError: (err) => show(err.message, "error"),
    });
    setPendingDeleteId(null);
  }

  const columns: TableColumn<ActionBinding>[] = [
    { key: "name", header: "Name" },
    { key: "database", header: "Database", render: (a) => dbName(a.database_id) },
    { key: "event", header: "Event", render: (a) => a.event_type },
    {
      key: "target", header: "Target",
      render: (a) =>
        a.target_type === "agent"
          ? `Agent: ${agName(a.agent_id ?? "")}`
          : `Workflow: ${wfName(a.workflow_id ?? "")}`,
    },
    { key: "active", header: "Active", render: (a) => (a.is_active ? "Yes" : "No") },
    {
      key: "actions", header: "",
      render: (a) => (
        <div style={{ display: "flex", gap: "var(--space-1)" }}>
          <Button variant="secondary" onClick={() => startEdit(a)}>Edit</Button>
          <Button variant="secondary" onClick={() => setPendingDeleteId(a.id)}>Delete</Button>
        </div>
      ),
    },
  ];

  function renderList() {
    if (query.isError) {
      return (
        <ErrorState
          message={query.error?.message ?? "Failed to load actions"}
          retry={<Button variant="secondary" onClick={() => query.refetch()}>Retry</Button>}
        />
      );
    }
    if (query.isLoading) return <Skeleton lines={3} height="24px" />;
    if (actions.length === 0) {
      return <EmptyState title="No actions yet" description="Create an action to run a workflow when a Mini-App Database receives new records." />;
    }
    return <Table<ActionBinding> columns={columns} rows={actions} rowId={(a) => a.id} caption="Actions" />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card
        title="Actions"
        subtitle="Run a Workflow automatically when a Mini-App Database row event fires."
        headerAction={<Button variant="primary" onClick={startCreate}>New action</Button>}
      >
        {renderList()}
      </Card>

      {draft && (
        <Card title={draft.id === null ? "Create action" : "Edit action"}>
          <form onSubmit={handleSubmit}>
            <FormField label="Name" required>
              <input
                id="vaic-field-name"
                className="vaic-form-input vaic-focusable"
                required
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
            </FormField>

            <div className="vaic-form-field">
              <label className="vaic-form-label" htmlFor="vaic-action-database">Mini-App Database</label>
              <select
                id="vaic-action-database" className="vaic-form-input vaic-focusable"
                value={draft.database_id} onChange={(e) => setDraft({ ...draft, database_id: e.target.value })}
              >
                <option value="">— Select a database —</option>
                {databases.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>

            <div className="vaic-form-field">
              <label className="vaic-form-label" htmlFor="vaic-action-event">Event</label>
              <select
                id="vaic-action-event" className="vaic-form-input vaic-focusable"
                value={draft.event_type}
                onChange={(e) => setDraft({ ...draft, event_type: e.target.value as ActionEventType })}
              >
                {EVENT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>

            <div className="vaic-form-field">
              <label className="vaic-form-label" htmlFor="vaic-action-target-type">Target type</label>
              <select
                id="vaic-action-target-type" className="vaic-form-input vaic-focusable"
                value={draft.target_type}
                onChange={(e) => setDraft({ ...draft, target_type: e.target.value as ActionTargetType })}
              >
                <option value="workflow">Workflow</option>
                <option value="agent">Agent</option>
              </select>
            </div>

            {draft.target_type === "workflow" ? (
              <div className="vaic-form-field">
                <label className="vaic-form-label" htmlFor="vaic-action-workflow">Workflow</label>
                <select
                  id="vaic-action-workflow" className="vaic-form-input vaic-focusable"
                  value={draft.workflow_id} onChange={(e) => setDraft({ ...draft, workflow_id: e.target.value })}
                >
                  <option value="">— Select a workflow —</option>
                  {workflows.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
                </select>
              </div>
            ) : (
              <div className="vaic-form-field">
                <label className="vaic-form-label" htmlFor="vaic-action-agent">Agent</label>
                <select
                  id="vaic-action-agent" className="vaic-form-input vaic-focusable"
                  value={draft.agent_id} onChange={(e) => setDraft({ ...draft, agent_id: e.target.value })}
                >
                  <option value="">— Select an agent —</option>
                  {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </div>
            )}

            <FormField
              label="Notify user IDs (comma-separated, optional)"
              helperText="Staff to notify. Leave blank to notify the action owner."
            >
              <input
                id="vaic-field-notify-user-ids-(comma-separated,-optional)"
                className="vaic-form-input vaic-focusable"
                value={draft.notify_user_ids}
                onChange={(e) => setDraft({ ...draft, notify_user_ids: e.target.value })}
              />
            </FormField>

            <label style={{ display: "inline-flex", gap: "var(--space-1)", alignItems: "center", fontSize: "var(--text-small)" }}>
              <input
                type="checkbox" checked={draft.is_active}
                onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })}
              />
              Active
            </label>

            <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-3)" }}>
              <Button variant="primary" type="submit" disabled={create.isPending || update.isPending}>
                {draft.id === null ? "Create" : "Save"}
              </Button>
              <Button variant="secondary" type="button" onClick={() => setDraft(null)}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      <ConfirmDialog
        open={pendingDeleteId !== null}
        title="Delete this action?"
        body="New records will no longer trigger the bound workflow. This cannot be undone."
        confirmLabel="Delete" cancelLabel="Cancel"
        onConfirm={confirmDelete} onCancel={() => setPendingDeleteId(null)}
      />
    </div>
  );
}
