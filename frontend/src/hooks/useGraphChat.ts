import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { usePersistentChatSession } from "./usePersistentChatSession";

export interface GraphChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: "pending" | "completed" | "failed";
  error?: { message: string } | null;
  metadata: Record<string, unknown>;
  modelName?: string | null;
}

export function useGraphChat(workflowId: string) {
  const queryClient = useQueryClient();
  const chat = usePersistentChatSession("graph_authoring", "workflow", workflowId);
  const messages: GraphChatMessage[] = (chat.messages.data ?? []).map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    status: message.status,
    error: message.error,
    metadata: message.metadata,
    modelName: message.model_name,
  }));
  const mutationCount = messages.filter((message) => message.metadata.action === "apply").length;
  useEffect(() => {
    if (mutationCount) {
      queryClient.invalidateQueries({ queryKey: ["workflow-graph", workflowId] });
    }
  }, [mutationCount, queryClient, workflowId]);
  return {
    messages,
    send: (content: string, attachmentIds: string[] = []) =>
      chat.send.mutate({ content, attachmentIds }),
    pending: chat.pending || chat.send.isPending,
    undo: (mutationId: string) => chat.undo.mutate(mutationId),
    error: chat.messages.error ?? chat.create.error ?? chat.send.error ?? chat.undo.error,
  };
}
