/* Persistent chat hook backed by the tenant-scoped Chat API. */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createChatSession,
  deleteChatSession,
  getChatModels,
  listChatMessages,
  listChatSessions,
  renameChatSession,
  sendChatMessage,
  switchChatModel,
  type ChatMessageDto,
} from "./chatApi";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  status: "pending" | "completed" | "failed";
  error?: { code: string; message: string } | null;
  metadata?: Record<string, unknown>;
  providerId?: string | null;
  modelName?: string | null;
  latencyMs?: number | null;
  replyToId?: string | null;
  attachmentIds?: string[];
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
  targetType: "agent" | "workflow";
  targetId: string;
  targetName?: string | null;
  providerId: string | null;
  modelName: string | null;
}

function mapMessage(message: ChatMessageDto): ChatMessage {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    createdAt: Date.parse(message.created_at),
    status: message.status,
    error: message.error,
    metadata: message.metadata,
    providerId: message.provider_id,
    modelName: message.model_name,
    latencyMs: message.latency_ms,
    replyToId: message.reply_to_id,
    attachmentIds: message.attachment_ids,
  };
}

export function useChat() {
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [targetNames, setTargetNames] = useState<Record<string, string>>({});
  const models = useQuery({ queryKey: ["chat-models"], queryFn: getChatModels });
  const sessions = useQuery({
    queryKey: ["chat-sessions", "execution"],
    queryFn: () => listChatSessions({ scope: "execution" }),
  });
  useEffect(() => {
    if (!activeId && sessions.data?.[0]) setActiveId(sessions.data[0].id);
    if (activeId && sessions.data && !sessions.data.some((item) => item.id === activeId)) {
      setActiveId(sessions.data[0]?.id ?? null);
    }
  }, [activeId, sessions.data]);

  const messageQuery = useQuery({
    queryKey: ["chat-messages", activeId],
    queryFn: () => listChatMessages(activeId!),
    enabled: Boolean(activeId),
    refetchInterval: (query) =>
      (query.state.data ?? []).some((message) => message.status === "pending") ? 1500 : false,
  });

  const conversations = useMemo<Conversation[]>(
    () =>
      (sessions.data ?? []).map((item) => ({
        id: item.id,
        title: item.title,
        messages: item.id === activeId ? (messageQuery.data ?? []).map(mapMessage) : [],
        createdAt: Date.parse(item.created_at),
        updatedAt: Date.parse(item.updated_at),
        targetType: item.target_type as "agent" | "workflow",
        targetId: item.target_id,
        targetName: targetNames[item.id] ?? null,
        providerId: item.provider_id,
        modelName: item.model_name,
      })),
    [sessions.data, activeId, messageQuery.data, targetNames],
  );
  const activeConversation = conversations.find((item) => item.id === activeId) ?? null;

  const create = useMutation({
    mutationFn: async ({ targetType, targetId, targetName }: { targetType: "agent" | "workflow"; targetId: string; targetName: string }) => {
      const firstProvider = models.data?.[0];
      const firstModel = firstProvider?.models[0];
      if (targetType === "agent" && (!firstProvider || !firstModel)) {
        throw new Error("Chưa cấu hình FPT AI hoặc Gemini");
      }
      return {
        targetName,
        session: await createChatSession({
          scope: "execution",
          target_type: targetType,
          target_id: targetId,
          provider_id: targetType === "workflow" ? null : firstProvider!.id,
          model_name: targetType === "workflow" ? null : firstModel!.name,
          title: targetName || "Cuộc trò chuyện mới",
        }),
      };
    },
    onSuccess: ({ session, targetName }) => {
      setTargetNames((current) => ({ ...current, [session.id]: targetName }));
      setActiveId(session.id);
      queryClient.invalidateQueries({ queryKey: ["chat-sessions", "execution"] });
    },
  });
  const remove = useMutation({
    mutationFn: deleteChatSession,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat-sessions", "execution"] }),
  });
  const rename = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => renameChatSession(id, title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat-sessions", "execution"] }),
  });
  const send = useMutation({
    mutationFn: ({ text, attachmentIds }: { text: string; attachmentIds: string[] }) =>
      sendChatMessage(activeId!, text, attachmentIds),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat-messages", activeId] }),
  });
  const changeModel = useMutation({
    mutationFn: ({ providerId, modelName }: { providerId: string; modelName: string }) =>
      switchChatModel(activeId!, providerId, modelName),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chat-sessions", "execution"] }),
  });

  const createConversation = useCallback(
    (targetType: "agent" | "workflow", targetId: string, targetName: string) =>
      create.mutate({ targetType, targetId, targetName }),
    [create],
  );
  const sendMessage = useCallback(
    (text: string, attachmentIds: string[] = []) => {
      if (activeId && text.trim()) send.mutate({ text: text.trim(), attachmentIds });
    },
    [activeId, send],
  );
  const isTyping = send.isPending || (messageQuery.data ?? []).some((item) => item.status === "pending");

  return {
    conversations,
    activeId,
    activeConversation,
    isTyping,
    models: models.data ?? [],
    error: sessions.error ?? messageQuery.error ?? create.error ?? send.error,
    selectConversation: setActiveId,
    createConversation,
    deleteConversation: (id: string) => remove.mutate(id),
    renameConversation: (id: string, title: string) => rename.mutate({ id, title }),
    sendMessage,
    switchModel: (providerId: string, modelName: string) =>
      changeModel.mutate({ providerId, modelName }),
  };
}
