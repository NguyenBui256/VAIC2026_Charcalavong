import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createChatSession,
  listChatMessages,
  listChatSessions,
  sendChatMessage,
  undoChatMutation,
  type ChatScope,
  type ChatTargetType,
} from "../lib/chatApi";

// Edit chats (workflow graph / mini-app) bind a session directly to the target.
// The UI selects neither an Agent nor a model — the backend applies a dedicated
// default system prompt per scope and fills a default model at session creation.
export function usePersistentChatSession(
  scope: ChatScope,
  targetType: ChatTargetType,
  targetId: string,
) {
  const queryClient = useQueryClient();
  const sessions = useQuery({
    queryKey: ["chat-sessions", scope, targetType, targetId],
    queryFn: () => listChatSessions({ scope, targetType, targetId }),
  });
  const session = sessions.data?.[0] ?? null;
  const create = useMutation({
    mutationFn: async () =>
      createChatSession({
        scope,
        target_type: targetType,
        target_id: targetId,
        title: targetType === "workflow" ? "Graph Chat" : "Mini-App Chat",
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat-sessions", scope, targetType, targetId] }),
  });

  useEffect(() => {
    if (sessions.data && sessions.data.length === 0 && !create.isPending && !create.isError) {
      create.mutate();
    }
  }, [sessions.data, create.isPending, create.isError]);

  const messages = useQuery({
    queryKey: ["chat-messages", session?.id],
    queryFn: () => listChatMessages(session!.id),
    enabled: Boolean(session),
    refetchInterval: (query) =>
      (query.state.data ?? []).some((message) => message.status === "pending") ? 1500 : false,
  });
  const send = useMutation({
    mutationFn: ({ content, attachmentIds }: { content: string; attachmentIds: string[] }) =>
      sendChatMessage(session!.id, content, attachmentIds),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat-messages", session?.id] }),
  });
  const undo = useMutation({
    mutationFn: undoChatMutation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-messages", session?.id] });
      queryClient.invalidateQueries({ queryKey: targetType === "workflow" ? ["workflow-graph", targetId] : ["mini-app", targetId] });
    },
  });
  const pending = (messages.data ?? []).some((message) => message.status === "pending");
  return { session, sessions, messages, send, undo, pending, create };
}
