/* Chat store for the UI shell — persists conversations to localStorage
 * and orchestrates mock bot replies with a typing effect.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { generateMockReply, streamText } from "./mockReply";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
}

export interface Conversation {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

const STORAGE_KEY = "vaic:chat:conversations";

function uid(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
}

function load(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as Conversation[]) : [];
  } catch {
    return [];
  }
}

function save(list: Conversation[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    // ignore quota / serialization errors — UI shell only
  }
}

/** Derive a conversation title from the first user message. */
function titleFrom(text: string): string {
  const t = text.trim().replace(/\s+/g, " ");
  return t.length > 40 ? `${t.slice(0, 40)}…` : t || "New chat";
}

export function useChat() {
  const initial = useRef<Conversation[]>(load());
  const [conversations, setConversations] = useState<Conversation[]>(initial.current);
  const [activeId, setActiveId] = useState<string | null>(
    initial.current[0]?.id ?? null,
  );
  const [isTyping, setIsTyping] = useState(false);
  const cancelRef = useRef<(() => void) | null>(null);

  // Persist on every change.
  useEffect(() => {
    save(conversations);
  }, [conversations]);

  // Cleanup any running stream on unmount.
  useEffect(() => {
    return () => cancelRef.current?.();
  }, []);

  const activeConversation =
    conversations.find((c) => c.id === activeId) ?? null;

  const selectConversation = useCallback((id: string) => {
    cancelRef.current?.();
    setIsTyping(false);
    setActiveId(id);
  }, []);

  const newConversation = useCallback(() => {
    cancelRef.current?.();
    setIsTyping(false);
    const now = Date.now();
    const conv: Conversation = {
      id: uid(),
      title: "New chat",
      messages: [],
      createdAt: now,
      updatedAt: now,
    };
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
  }, []);

  const deleteConversation = useCallback(
    (id: string) => {
      cancelRef.current?.();
      setIsTyping(false);
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id);
        setActiveId((cur) => (cur === id ? next[0]?.id ?? null : cur));
        return next;
      });
    },
    [],
  );

  const renameConversation = useCallback((id: string, title: string) => {
    setConversations((prev) =>
      prev.map((c) =>
        c.id === id ? { ...c, title: title.trim() || c.title } : c,
      ),
    );
  }, []);

  // Helper: mutate messages of a conversation by id.
  const patchMessages = useCallback(
    (id: string, fn: (msgs: ChatMessage[]) => ChatMessage[]) => {
      setConversations((prev) =>
        prev.map((c) =>
          c.id === id
            ? { ...c, messages: fn(c.messages), updatedAt: Date.now() }
            : c,
        ),
      );
    },
    [],
  );

  const sendMessage = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isTyping) return;

      // Ensure there is an active conversation.
      let convId = activeId;
      if (!convId) {
        const now = Date.now();
        const conv: Conversation = {
          id: uid(),
          title: titleFrom(trimmed),
          messages: [],
          createdAt: now,
          updatedAt: now,
        };
        convId = conv.id;
        setConversations((prev) => [conv, ...prev]);
        setActiveId(conv.id);
      }
      const id = convId;

      const userMsg: ChatMessage = {
        id: uid(),
        role: "user",
        content: trimmed,
        createdAt: Date.now(),
      };
      const assistantId = uid();
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        createdAt: Date.now(),
      };

      // Append user + empty assistant; set title if it was default.
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== id) return c;
          const nextTitle =
            c.title === "New chat" || c.messages.length === 0
              ? titleFrom(trimmed)
              : c.title;
          return {
            ...c,
            title: nextTitle,
            messages: [...c.messages, userMsg, assistantMsg],
            updatedAt: Date.now(),
          };
        }),
      );

      // Stream the mock reply into the assistant message.
      setIsTyping(true);
      const full = generateMockReply(trimmed);
      cancelRef.current = streamText(
        full,
        (partial) => {
          patchMessages(id, (msgs) =>
            msgs.map((m) =>
              m.id === assistantId ? { ...m, content: partial } : m,
            ),
          );
        },
        () => {
          setIsTyping(false);
          cancelRef.current = null;
        },
      );
    },
    [activeId, isTyping, patchMessages],
  );

  return {
    conversations,
    activeId,
    activeConversation,
    isTyping,
    selectConversation,
    newConversation,
    deleteConversation,
    renameConversation,
    sendMessage,
  };
}
