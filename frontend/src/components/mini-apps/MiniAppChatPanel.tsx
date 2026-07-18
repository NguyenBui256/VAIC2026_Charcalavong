/* Chat panel (left column of the mini-app detail page). Sends a natural-language
 * instruction to POST /mini-apps/{id}/edit, which LLM-revises the app's schema/
 * ui_spec and rebuilds. Client-side message history (localStorage per app);
 * assistant reply is fake-streamed. Input disabled while the app is rebuilding. */
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button, useToast } from "../ui";
import { editMiniApp, type MiniApp } from "../../lib/miniAppsApi";
import { streamText } from "../../lib/streamText";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

const WELCOME: ChatMessage = {
  role: "assistant",
  text:
    "Hi! Tell me how to change this app — e.g. \"add a due_date date field\", " +
    "\"show records as cards\", or \"remove the delete action\". I'll update it and rebuild the preview.",
};

function storageKey(appId: string): string {
  return `vaic:miniapp-chat:${appId}`;
}

function loadMessages(appId: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(storageKey(appId));
    if (raw) return JSON.parse(raw) as ChatMessage[];
  } catch {
    /* ignore corrupt storage */
  }
  return [WELCOME];
}

export interface MiniAppChatPanelProps {
  app: MiniApp;
  appId: string;
}

export default function MiniAppChatPanel({ app, appId }: MiniAppChatPanelProps) {
  const qc = useQueryClient();
  const { show } = useToast();
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadMessages(appId));
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState<string | null>(null);
  const cancelRef = useRef<(() => void) | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const isRebuilding = app.build_status === "pending" || app.build_status === "building";

  useEffect(() => {
    try {
      localStorage.setItem(storageKey(appId), JSON.stringify(messages));
    } catch {
      /* ignore quota errors */
    }
  }, [messages, appId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, streaming]);

  useEffect(() => () => cancelRef.current?.(), []);

  const edit = useMutation<{ message: string; app: MiniApp }, Error, string>({
    mutationFn: (instruction) => editMiniApp(appId, instruction),
    onSuccess: (data) => {
      // Reflect the pending/rebuild status immediately, then poll picks up ready.
      qc.setQueryData(["mini-app", appId], data.app);
      qc.invalidateQueries({ queryKey: ["mini-app", appId] });
      // Fake-stream the assistant reply for feel.
      cancelRef.current?.();
      setStreaming("");
      cancelRef.current = streamText(
        data.message,
        (partial) => setStreaming(partial),
        () => {
          setStreaming(null);
          setMessages((m) => [...m, { role: "assistant", text: data.message }]);
        },
      );
    },
    onError: (err) => {
      const text = `Sorry — I couldn't apply that: ${err.message}`;
      setMessages((m) => [...m, { role: "assistant", text }]);
      show(err.message || "Edit failed", "error");
    },
  });

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const instruction = input.trim();
    if (!instruction || edit.isPending || isRebuilding) return;
    setMessages((m) => [...m, { role: "user", text: instruction }]);
    setInput("");
    edit.mutate(instruction);
  }

  return (
    <div
      data-testid="vaic-miniapp-chat"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-control)",
        background: "var(--color-surface)",
        overflow: "hidden",
      }}
    >
      <div
        ref={scrollRef}
        style={{ flex: 1, overflowY: "auto", padding: "var(--space-3)", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}
      >
        {messages.map((m, i) => (
          <ChatBubble key={i} role={m.role} text={m.text} />
        ))}
        {streaming !== null && <ChatBubble role="assistant" text={streaming || "…"} />}
        {edit.isPending && streaming === null && <ChatBubble role="assistant" text="Thinking…" />}
      </div>

      {isRebuilding && (
        <div
          className="vaic-inline-alert"
          role="status"
          style={{ margin: "0 var(--space-3) var(--space-2)", color: "var(--color-text-tertiary)", fontSize: "var(--text-small)" }}
        >
          Rebuilding the preview…
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        style={{ display: "flex", gap: "var(--space-2)", padding: "var(--space-3)", borderTop: "1px solid var(--color-border)" }}
      >
        <input
          className="vaic-form-input vaic-focusable"
          style={{ flex: 1 }}
          placeholder={isRebuilding ? "Rebuilding…" : "Describe a change to this app…"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={edit.isPending || isRebuilding}
          data-testid="vaic-miniapp-chat-input"
        />
        <Button variant="primary" type="submit" disabled={!input.trim() || edit.isPending || isRebuilding}>
          Send
        </Button>
      </form>
    </div>
  );
}

function ChatBubble({ role, text }: { role: "user" | "assistant"; text: string }) {
  const isUser = role === "user";
  return (
    <div
      style={{
        alignSelf: isUser ? "flex-end" : "flex-start",
        maxWidth: "85%",
        padding: "var(--space-2) var(--space-3)",
        borderRadius: "var(--radius-control)",
        background: isUser ? "var(--color-primary-soft)" : "var(--color-surface-muted)",
        color: "var(--color-text)",
        fontSize: "var(--text-body)",
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}
    >
      {text}
    </div>
  );
}
