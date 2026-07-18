/* One chat bubble: user (right, primary-soft) or assistant (left, muted).
 * Assistant bubbles render markdown + a copy button; show timestamp.
 */

import { useState } from "react";
import { Copy, Check } from "lucide-react";
import type { ChatMessage } from "../../lib/chatStore";
import MarkdownMessage from "./markdown-message";

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard unavailable — ignore silently
    }
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: isUser ? "flex-end" : "flex-start",
        gap: "var(--space-1)",
        margin: "var(--space-3) 0",
      }}
    >
      <div
        style={{
          maxWidth: "80%",
          padding: "var(--space-3) var(--space-4)",
          borderRadius: "var(--radius-control, 12px)",
          background: isUser
            ? "var(--color-primary-soft)"
            : "var(--color-surface-muted)",
          color: "var(--color-text-primary)",
          whiteSpace: isUser ? "pre-wrap" : undefined,
          wordBreak: "break-word",
        }}
      >
        {isUser ? message.content : <MarkdownMessage content={message.content} />}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2)",
          fontSize: "var(--text-caption)",
          color: "var(--color-text-tertiary)",
          padding: "0 var(--space-1)",
        }}
      >
        <span>{formatTime(message.createdAt)}</span>
        {!isUser && message.content && (
          <button
            type="button"
            onClick={handleCopy}
            aria-label={copied ? "Copied" : "Copy message"}
            title={copied ? "Copied" : "Copy"}
            style={{
              display: "inline-flex",
              alignItems: "center",
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "inherit",
              padding: 0,
            }}
          >
            {copied ? <Check size={13} strokeWidth={1.5} /> : <Copy size={13} strokeWidth={1.5} />}
          </button>
        )}
      </div>
    </div>
  );
}
