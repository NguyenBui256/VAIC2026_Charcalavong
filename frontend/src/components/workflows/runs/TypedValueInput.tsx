/* 3E — controlled input for a typed value: a type selector (JSON | Text |
 * File) + the matching editor. File selection uploads immediately and stores
 * the returned ref on the draft. The parent resolves the draft at submit
 * (resolveDraft) so JSON parsing / file-required checks happen on submit.
 */
import { useState } from "react";
import { useToast } from "../../ui";
import { uploadWorkflowFile, type TypedValueDraft } from "../../../lib/typedValue";

export interface TypedValueInputProps {
  value: TypedValueDraft;
  onChange: (draft: TypedValueDraft) => void;
}

export default function TypedValueInput({ value, onChange }: TypedValueInputProps) {
  const toast = useToast();
  const [uploading, setUploading] = useState(false);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const ref = await uploadWorkflowFile(f);
      onChange({ ...value, file: ref });
    } catch (err) {
      toast.show((err as Error).message, "error");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      <select
        className="vaic-form-input vaic-focusable"
        value={value.type}
        onChange={(e) =>
          onChange({ ...value, type: e.target.value as TypedValueDraft["type"] })
        }
      >
        <option value="json">JSON</option>
        <option value="text">Text</option>
        <option value="file">File</option>
      </select>

      {value.type === "json" && (
        <textarea
          className="vaic-form-input vaic-focusable"
          value={value.jsonText}
          onChange={(e) => onChange({ ...value, jsonText: e.target.value })}
          rows={3}
        />
      )}

      {value.type === "text" && (
        <textarea
          className="vaic-form-input vaic-focusable"
          placeholder="Plain text"
          value={value.text}
          onChange={(e) => onChange({ ...value, text: e.target.value })}
          rows={3}
        />
      )}

      {value.type === "file" && (
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <input type="file" onChange={onFile} disabled={uploading} />
          {uploading && <span className="text-body">Uploading…</span>}
          {value.file && (
            <span className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
              {value.file.name} ({(value.file.size / 1024).toFixed(1)} KB)
            </span>
          )}
        </div>
      )}
    </div>
  );
}
