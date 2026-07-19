import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createChatSession,
  getChatModels,
  listChatMessages,
  listChatSessions,
  sendChatMessage,
  switchChatModel,
  undoChatMutation,
  type ChatScope,
  type ChatTargetType,
} from "../lib/chatApi";

export function usePersistentChatSession(
  scope: ChatScope,
  targetType: ChatTargetType,
  targetId: string,
) {
  const queryClient = useQueryClient();
  const models = useQuery({ queryKey: ["chat-models"], queryFn: getChatModels });
  const sessions = useQuery({
    queryKey: ["chat-sessions", scope, targetType, targetId],
    queryFn: () => listChatSessions({ scope, targetType, targetId }),
  });
  const session = sessions.data?.[0] ?? null;
  const create = useMutation({
    mutationFn: async () => {
      const firstProvider = models.data?.[0];
      const firstModel = firstProvider?.models[0];
      if (!firstProvider || !firstModel) throw new Error("Chưa cấu hình FPT AI hoặc Gemini");
      return createChatSession({
        scope,
        target_type: targetType,
        target_id: targetId,
        provider_id: firstProvider.id,
        model_name: firstModel.name,
        title: targetType === "workflow" ? "Graph Chat" : "Mini-App Chat",
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat-sessions", scope, targetType, targetId] }),
  });

  useEffect(() => {
    if (models.data && sessions.data && sessions.data.length === 0 && !create.isPending && !create.isError) {
      create.mutate();
    }
  }, [models.data, sessions.data, create.isPending, create.isError]);

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
  const changeModel = useMutation({
    mutationFn: ({ providerId, modelName }: { providerId: string; modelName: string }) =>
      switchChatModel(session!.id, providerId, modelName),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat-sessions", scope, targetType, targetId] }),
  });
  const undo = useMutation({
    mutationFn: undoChatMutation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-messages", session?.id] });
      queryClient.invalidateQueries({ queryKey: targetType === "workflow" ? ["workflow-graph", targetId] : ["mini-app", targetId] });
    },
  });
  const pending = (messages.data ?? []).some((message) => message.status === "pending");
  return { models, session, sessions, messages, send, changeModel, undo, pending, create };
}
