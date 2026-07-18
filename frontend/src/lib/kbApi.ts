/* Shared pool — tenant-level Knowledge Base API layer.
 *
 * Typed wrappers around apiFetch for the pool KB document endpoints:
 * POST/GET /kb/documents, DELETE /kb/documents/{docId}. apiFetch injects
 * JWT + tenant headers and unwraps the {data,error,meta} envelope; multipart
 * bodies skip the JSON Content-Type override (api.ts).
 */

import { apiFetch } from "./api";

export type KbStatus = "processing" | "indexed" | "failed";

/** Mirrors the backend `serialize_document` response shape. */
export interface KbDocument {
  id: string;
  owner_id: string;
  department_id: string | null;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: KbStatus;
  failure_reason: string | null;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

/** Single source of truth for the client-side 20MB + type gate. */
export const KB_MAX_BYTES = 20 * 1024 * 1024;

export const KB_ACCEPTED_EXTENSIONS = [".pdf", ".txt", ".md", ".markdown", ".docx"];

export const KB_ACCEPTED_MIME_TYPES = new Set([
  "application/pdf",
  "text/plain",
  "text/markdown",
  "text/x-markdown",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);

export function listKbDocuments(): Promise<KbDocument[]> {
  return apiFetch<KbDocument[]>(`/kb/documents`);
}

export function uploadKbDocument(file: File): Promise<KbDocument> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<KbDocument>(`/kb/documents`, {
    method: "POST",
    body: form,
  });
}

export function deleteKbDocument(documentId: string): Promise<{ id: string }> {
  return apiFetch<{ id: string }>(`/kb/documents/${documentId}`, {
    method: "DELETE",
  });
}
