/* Shared pool — agent grant API layer.
 *
 * Attach/detach shared pool resources (Tools, Knowledge Base documents) onto
 * a specific agent: GET/POST /agents/{id}/tools, DELETE .../tools/{toolId};
 * GET/POST /agents/{id}/kb-documents, DELETE .../kb-documents/{docId}.
 * apiFetch injects JWT + tenant headers and unwraps the {data,error,meta}
 * envelope.
 */

import { apiFetch } from "./api";
import type { Tool } from "./toolsApi";
import type { KbDocument } from "./kbApi";

export function listAgentTools(agentId: string): Promise<Tool[]> {
  return apiFetch<Tool[]>(`/agents/${agentId}/tools`);
}

export function attachAgentTool(agentId: string, toolId: string): Promise<unknown> {
  return apiFetch(`/agents/${agentId}/tools`, {
    method: "POST",
    body: JSON.stringify({ tool_id: toolId }),
  });
}

export function detachAgentTool(agentId: string, toolId: string): Promise<unknown> {
  return apiFetch(`/agents/${agentId}/tools/${toolId}`, {
    method: "DELETE",
  });
}

export function listAgentKb(agentId: string): Promise<KbDocument[]> {
  return apiFetch<KbDocument[]>(`/agents/${agentId}/kb-documents`);
}

export function attachAgentKb(agentId: string, docId: string): Promise<unknown> {
  return apiFetch(`/agents/${agentId}/kb-documents`, {
    method: "POST",
    body: JSON.stringify({ document_id: docId }),
  });
}

export function detachAgentKb(agentId: string, docId: string): Promise<unknown> {
  return apiFetch(`/agents/${agentId}/kb-documents/${docId}`, {
    method: "DELETE",
  });
}
