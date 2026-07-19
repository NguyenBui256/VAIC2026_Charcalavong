import { apiFetch, authHeaders, ApiError } from "./api";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export type ChatScope = "execution" | "graph_authoring" | "mini_app_edit";
export type ChatTargetType = "agent" | "workflow" | "mini_app";

export interface ChatModel {
  name: string;
  context_window: number;
}

export interface ChatProvider {
  id: string;
  label: string;
  configured: boolean;
  models: ChatModel[];
}

export interface ChatSessionDto {
  id: string;
  scope: ChatScope;
  target_type: ChatTargetType;
  target_id: string;
  provider_id: string | null;
  model_name: string | null;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageDto {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  status: "pending" | "completed" | "failed";
  client_message_id: string | null;
  reply_to_id: string | null;
  provider_id: string | null;
  model_name: string | null;
  usage: { input_tokens: number | null; output_tokens: number | null };
  latency_ms: number | null;
  trace_id: string | null;
  metadata: Record<string, unknown>;
  error: { code: string; message: string } | null;
  attachment_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface ChatAttachmentDto {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  extraction_status: "extracting" | "ready" | "failed";
  extraction_error: string | null;
  created_at: string;
}

export function getChatModels(): Promise<ChatProvider[]> {
  return apiFetch("/chat/models");
}

export function listChatSessions(params: {
  scope?: ChatScope;
  targetType?: ChatTargetType;
  targetId?: string;
} = {}): Promise<ChatSessionDto[]> {
  const query = new URLSearchParams();
  if (params.scope) query.set("scope", params.scope);
  if (params.targetType) query.set("target_type", params.targetType);
  if (params.targetId) query.set("target_id", params.targetId);
  return apiFetch(`/chat/sessions${query.size ? `?${query}` : ""}`);
}

export function createChatSession(body: {
  scope: ChatScope;
  target_type: ChatTargetType;
  target_id: string;
  provider_id?: string | null;
  model_name?: string | null;
  title: string;
}): Promise<ChatSessionDto> {
  return apiFetch("/chat/sessions", { method: "POST", body: JSON.stringify(body) });
}

export function renameChatSession(id: string, title: string): Promise<ChatSessionDto> {
  return apiFetch(`/chat/sessions/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export function deleteChatSession(id: string): Promise<{ deleted: string }> {
  return apiFetch(`/chat/sessions/${id}`, { method: "DELETE" });
}

export function switchChatModel(
  id: string,
  providerId: string,
  modelName: string,
): Promise<ChatSessionDto> {
  return apiFetch(`/chat/sessions/${id}/model`, {
    method: "PATCH",
    body: JSON.stringify({ provider_id: providerId, model_name: modelName }),
  });
}

export function listChatMessages(id: string): Promise<ChatMessageDto[]> {
  return apiFetch(`/chat/sessions/${id}/messages`);
}

export function sendChatMessage(
  id: string,
  content: string,
  attachmentIds: string[] = [],
): Promise<{ user: ChatMessageDto; assistant: ChatMessageDto }> {
  return apiFetch(`/chat/sessions/${id}/messages`, {
    method: "POST",
    body: JSON.stringify({
      content,
      client_message_id: crypto.randomUUID(),
      attachment_ids: attachmentIds,
    }),
  });
}

export function getChatAttachment(id: string): Promise<ChatAttachmentDto> {
  return apiFetch(`/chat/attachments/${id}`);
}

export function deleteChatAttachment(id: string): Promise<{ deleted: string }> {
  return apiFetch(`/chat/attachments/${id}`, { method: "DELETE" });
}

export function undoChatMutation(id: string): Promise<Record<string, unknown>> {
  return apiFetch(`/chat/mutations/${id}/undo`, { method: "POST" });
}

export function uploadChatAttachment(
  file: File,
  onProgress: (percent: number) => void,
): Promise<ChatAttachmentDto> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/chat/attachments`);
    const headers = authHeaders();
    delete headers["Content-Type"];
    for (const [key, value] of Object.entries(headers)) xhr.setRequestHeader(key, value);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onerror = () => reject(new ApiError("Upload failed", 0, "NETWORK_ERROR"));
    xhr.onload = () => {
      let body: any;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        reject(new ApiError("Upload returned an invalid response", xhr.status, "INVALID_RESPONSE"));
        return;
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(new ApiError(body?.error?.message ?? "Upload failed", xhr.status, body?.error?.code ?? "UPLOAD_FAILED"));
        return;
      }
      resolve((body?.data ?? body) as ChatAttachmentDto);
    };
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}
