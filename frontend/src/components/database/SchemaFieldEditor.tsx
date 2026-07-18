/* Editor for a Mini-App Database entity_schema: a list of fields
 * (name, type, required, label; comma-separated options when type=enum). */
import { useState } from "react";
import { Trash2, Plus } from "lucide-react";
import { Button } from "../ui";
import { ICON_STROKE_WIDTH } from "../../lib/icons";
import type { EntitySchema, FieldType, SchemaField } from "../../lib/miniAppDatabasesApi";

const FIELD_TYPES: FieldType[] = ["string", "longtext", "integer", "number", "boolean", "date", "enum"];

/* On a type change, clear type-specific attributes that are no longer valid for the new
 * type (backend rejects e.g. `options` left over from a prior `enum` type with a 422).
 * SchemaField only carries `options` as a type-specific attribute today, so that's all
 * that needs clearing; add min/max/minLength/maxLength/pattern here if SchemaField ever
 * grows those fields. */
function attrsForTypeChange(newType: FieldType): Partial<SchemaField> {
  if (newType === "enum") return { options: [] };
  return { options: undefined };
}

export interface SchemaFieldEditorProps {
  value: EntitySchema;
  onChange: (schema: EntitySchema) => void;
}

interface FieldRowProps {
  field: SchemaField;
  index: number;
  onChange: (patch: Partial<SchemaField>) => void;
  onRemove: () => void;
}

/* Per-field row. Keeps a local `optionsText` string for the enum options input so the
 * user can type freely (e.g. trailing commas while starting a new option) without the
 * displayed value snapping back to the parsed+rejoined array on every keystroke. */
function FieldRow({ field: f, index: idx, onChange, onRemove }: FieldRowProps) {
  const [optionsText, setOptionsText] = useState(() => (f.options ?? []).join(", "));

  function handleOptionsChange(text: string) {
    setOptionsText(text);
    onChange({ options: text.split(",").map((s) => s.trim()).filter(Boolean) });
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 1.2fr auto auto", gap: "var(--space-2)", alignItems: "center" }}>
      <input
        className="vaic-form-input vaic-focusable" placeholder="field_name"
        value={f.name} onChange={(e) => onChange({ name: e.target.value })}
      />
      <select
        className="vaic-form-input vaic-focusable"
        value={f.type} onChange={(e) => {
          const newType = e.target.value as FieldType;
          onChange({ type: newType, ...attrsForTypeChange(newType) });
        }}
      >
        {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
      </select>
      {f.type === "enum" ? (
        <input
          className="vaic-form-input vaic-focusable" placeholder="opt1, opt2, opt3"
          value={optionsText}
          onChange={(e) => handleOptionsChange(e.target.value)}
        />
      ) : (
        <input
          className="vaic-form-input vaic-focusable" placeholder="Label (optional)"
          value={f.label ?? ""} onChange={(e) => onChange({ label: e.target.value || undefined })}
        />
      )}
      <label style={{ display: "inline-flex", gap: "var(--space-1)", alignItems: "center", fontSize: "var(--text-small)" }}>
        <input type="checkbox" checked={Boolean(f.required)} onChange={(e) => onChange({ required: e.target.checked })} />
        Required
      </label>
      <Button variant="icon" aria-label={`Remove field ${f.name || idx + 1}`} onClick={onRemove}>
        <Trash2 size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
      </Button>
    </div>
  );
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
        <FieldRow
          key={idx}
          field={f}
          index={idx}
          onChange={(patch) => update(idx, patch)}
          onRemove={() => remove(idx)}
        />
      ))}
      <div>
        <Button variant="secondary" onClick={add}>
          <Plus size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" /> Add field
        </Button>
      </div>
    </div>
  );
}
