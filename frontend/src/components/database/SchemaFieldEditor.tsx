/* Editor for a Mini-App Database entity_schema: a list of fields
 * (name, type, required, label; comma-separated options when type=enum). */
import { Trash2, Plus } from "lucide-react";
import { Button } from "../ui";
import { ICON_STROKE_WIDTH } from "../../lib/icons";
import type { EntitySchema, FieldType, SchemaField } from "../../lib/miniAppDatabasesApi";

const FIELD_TYPES: FieldType[] = ["string", "longtext", "integer", "number", "boolean", "date", "enum"];

export interface SchemaFieldEditorProps {
  value: EntitySchema;
  onChange: (schema: EntitySchema) => void;
}

export default function SchemaFieldEditor({ value, onChange }: SchemaFieldEditorProps) {
  const fields = value.fields;

  function update(idx: number, patch: Partial<SchemaField>) {
    const next = fields.map((f, i) => (i === idx ? { ...f, ...patch } : f));
    onChange({ ...value, fields: next });
  }
  function add() {
    onChange({ ...value, fields: [...fields, { name: "", type: "string", required: false }] });
  }
  function remove(idx: number) {
    onChange({ ...value, fields: fields.filter((_, i) => i !== idx) });
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      {fields.map((f, idx) => (
        <div key={idx} style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 1.2fr auto auto", gap: "var(--space-2)", alignItems: "center" }}>
          <input
            className="vaic-form-input vaic-focusable" placeholder="field_name"
            value={f.name} onChange={(e) => update(idx, { name: e.target.value })}
          />
          <select
            className="vaic-form-input vaic-focusable"
            value={f.type} onChange={(e) => update(idx, { type: e.target.value as FieldType })}
          >
            {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          {f.type === "enum" ? (
            <input
              className="vaic-form-input vaic-focusable" placeholder="opt1, opt2, opt3"
              value={(f.options ?? []).join(", ")}
              onChange={(e) => update(idx, { options: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
            />
          ) : (
            <input
              className="vaic-form-input vaic-focusable" placeholder="Label (optional)"
              value={f.label ?? ""} onChange={(e) => update(idx, { label: e.target.value || undefined })}
            />
          )}
          <label style={{ display: "inline-flex", gap: "var(--space-1)", alignItems: "center", fontSize: "var(--text-small)" }}>
            <input type="checkbox" checked={Boolean(f.required)} onChange={(e) => update(idx, { required: e.target.checked })} />
            Required
          </label>
          <Button variant="icon" aria-label={`Remove field ${f.name || idx + 1}`} onClick={() => remove(idx)}>
            <Trash2 size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
          </Button>
        </div>
      ))}
      <div>
        <Button variant="secondary" onClick={add}>
          <Plus size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" /> Add field
        </Button>
      </div>
    </div>
  );
}
