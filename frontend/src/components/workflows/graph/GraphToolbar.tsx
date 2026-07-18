/* 3D — editor toolbar: add/delete/save/reset + inline validation error. */
import { Button } from "../../ui";

export interface GraphToolbarProps {
  onAddNode: () => void;
  onDeleteSelected: () => void;
  onSave: () => void;
  onReset: () => void;
  saving: boolean;
  dirty: boolean;
  error: string | null;
}

export default function GraphToolbar({
  onAddNode,
  onDeleteSelected,
  onSave,
  onReset,
  saving,
  dirty,
  error,
}: GraphToolbarProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <Button variant="secondary" onClick={onAddNode}>Add node</Button>
        <Button variant="ghost" onClick={onDeleteSelected}>Delete selected</Button>
        <Button variant="ghost" onClick={onReset} disabled={!dirty || saving}>Reset</Button>
        <Button variant="primary" onClick={onSave} disabled={!dirty || saving || Boolean(error)}>
          {saving ? "Saving…" : "Save graph"}
        </Button>
      </div>
      {error && (
        <div className="vaic-inline-alert" role="alert">{error}</div>
      )}
    </div>
  );
}
