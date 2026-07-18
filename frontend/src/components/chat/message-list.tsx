/* Scrollable list of message bubbles. Auto-scrolls to newest.
 * Shows an empty state and a "typing…" indicator when the bot is replying.
 */

import { useEffect, useRef } from "react";
import type { ChatMessage } from "../../lib/chatStore";
import MessageBubble from "./message-bubble";

interface Props {
  messages: ChatMessage[];
  isTyping: boolean;
}

export default function MessageList({ messages, isTyping }: Props) {
  const endRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll on new content / typing progress.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isTyping]);

  const lastAssistantEmpty =
    isTyping &&
    messages.length > 0 &&
    messages[messages.length - 1].role === "assistant" &&
    messages[messages.length - 1].content === "";

  if (messages.length === 0) {
    return (
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--color-text-tertiary)",
        }}
      >
        <p className="text-body">Bắt đầu cuộc trò chuyện…</p>
      </div>
    );
  }

  return (
    <div
      style={{
        flex: 1,
        overflowY: "auto",
        padding: "var(--space-4) var(--space-6)",
      }}
    >
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}
      {lastAssistantEmpty && (
        <p
          className="text-caption"
          style={{ color: "var(--color-text-tertiary)", margin: "var(--space-2) 0" }}
        >
          Đang trả lời…
        </p>
      )}
      <div ref={endRef} />
    </div>
  );
}
