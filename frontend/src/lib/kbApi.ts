/* Story 2.4 — Knowledge Base API layer.
 *
 * Typed wrappers around apiFetch for the KB document endpoints delivered by
 * this story: POST/GET /agents/{id}/kb/documents, DELETE .../{docId}.
 * apiFetch injects JWT + tenant headers and unwraps the {data,error,meta}
 * envelope; multipart bodies skip the JSON Content-Type override (api.ts).
 */

import { apiFetch } from "./api";

export type KbStatus = "processing" | "indexed" | "failed";

/** Mirrors the Story 2.4 `serialize_document` response shape. */
export interface KbDocument {
  id: string;
  agent_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: KbStatus;
  failure_reason: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

/** AC3 — single source of truth for the client-side 20MB + type gate. */
export const KB_MAX_BYTES = 20 * 1024 * 1024;

export const KB_ACCEPTED_EXTENSIONS = [".pdf", ".txt", ".md", ".markdown", ".docx"];

export const KB_ACCEPTED_MIME_TYPES = new Set([
  "application/pdf",
  "text/plain",
  "text/markdown",
  "text/x-markdown",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);

export function listKbDocuments(agentId: string): Promise<KbDocument[]> {
  return apiFetch<KbDocument[]>(`/agents/${agentId}/kb/documents`);
}

export function uploadKbDocument(agentId: string, file: File): Promise<KbDocument> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<KbDocument>(`/agents/${agentId}/kb/documents`, {
    method: "POST",
    body: form,
  });
}

export function deleteKbDocument(agentId: string, documentId: string): Promise<{ id: string }> {
  return apiFetch<{ id: string }>(`/agents/${agentId}/kb/documents/${documentId}`, {
    method: "DELETE",
  });
}
