/* 3E — typed workflow I/O values (json | text | file) + file upload/download.
 * Untyped legacy/agent values normalize to {type:"json"}. File download is a
 * JWT-authed blob fetch (a bare <a href> would not carry the Authorization
 * header the protected endpoint requires).
 */
import { apiFetch, authHeaders } from "./api";

export interface FileRef {
  file_id: string;
  name: string;
  mime: string;
  size: number;
}

export type TypedValue =
  | { type: "json"; value: unknown }
  | { type: "text"; value: string }
  | ({ type: "file" } & FileRef);

/** Normalize any stored value to a TypedValue (legacy/agent dicts → json). */
export function toTyped(raw: unknown): TypedValue {
  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const t = (raw as { type?: unknown }).type;
    const r = raw as Record<string, unknown>;
    if (t === "text" && typeof r.value === "string") {
      return { type: "text", value: r.value };
    }
    if (t === "file" && typeof r.file_id === "string") {
      return {
        type: "file",
        file_id: r.file_id as string,
        name: String(r.name ?? "file"),
        mime: String(r.mime ?? "application/octet-stream"),
        size: Number(r.size ?? 0),
      };
    }
    if (t === "json" && "value" in r) {
      return { type: "json", value: r.value };
    }
  }
  return { type: "json", value: raw };
}

/** Editing draft held by TypedValueInput; resolved at submit. */
export interface TypedValueDraft {
  type: "json" | "text" | "file";
  jsonText: string;
  text: string;
  file: FileRef | null;
}

export function emptyDraft(): TypedValueDraft {
  return { type: "json", jsonText: "{}", text: "", file: null };
}

export function resolveDraft(
  d: TypedValueDraft,
): { ok: true; value: TypedValue } | { ok: false; error: string } {
  if (d.type === "json") {
    try {
      return { ok: true, value: { type: "json", value: JSON.parse(d.jsonText) } };
    } catch {
      return { ok: false, error: "Input must be valid JSON" };
    }
  }
  if (d.type === "text") {
    return { ok: true, value: { type: "text", value: d.text } };
  }
  if (!d.file) return { ok: false, error: "Choose a file to upload" };
  return { ok: true, value: { type: "file", ...d.file } };
}

export async function uploadWorkflowFile(file: File): Promise<FileRef> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await apiFetch<{ id: string; name: string; mime: string; size: number }>(
    "/workflows/files",
    { method: "POST", body: fd },
  );
  return { file_id: r.id, name: r.name, mime: r.mime, size: r.size };
}

/** Download via authed blob fetch (protected endpoint needs the JWT header). */
export async function downloadWorkflowFile(ref: FileRef): Promise<void> {
  const resp = await fetch(`/workflows/files/${ref.file_id}`, {
    headers: authHeaders(),
  });
  if (!resp.ok) throw new Error("Download failed");
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = ref.name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
