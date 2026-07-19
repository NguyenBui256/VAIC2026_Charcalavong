import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "../ui";
import type { MiniApp } from "../../lib/miniAppsApi";
import { usePersistentChatSession } from "../../hooks/usePersistentChatSession";
import AttachmentPicker from "../chat/attachment-picker";
import ModelSelector from "../chat/model-selector";

export interface MiniAppChatPanelProps {
  app: MiniApp;
  appId: string;
}

export default function MiniAppChatPanel({ app, appId }: MiniAppChatPanelProps) {
  const queryClient = useQueryClient();
  const chat = usePersistentChatSession("mini_app_edit", "mini_app", appId);
  const [input, setInput] = useState("");
  const [attachmentIds, setAttachmentIds] = useState<string[]>([]);
  const [attachmentsReady, setAttachmentsReady] = useState(true);
  const [attachmentEpoch, setAttachmentEpoch] = useState(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const messages = chat.messages.data ?? [];
  const isRebuilding = app.build_status === "pending" || app.build_status === "building";
  const applyCount = messages.filter((message) => message.metadata.action === "apply").length;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);
  useEffect(() => {
    if (applyCount) queryClient.invalidateQueries({ queryKey: ["mini-app", appId] });
  }, [applyCount, appId, queryClient]);

  const onAttachmentsChange = useCallback((ids: string[], ready: boolean) => {
    setAttachmentIds(ids);
    setAttachmentsReady(ready);
  }, []);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = input.trim();
    if (!content || chat.pending || !attachmentsReady || !chat.session) return;
    chat.send.mutate({ content, attachmentIds });
    setInput("");
    setAttachmentIds([]);
    setAttachmentsReady(true);
    setAttachmentEpoch((current) => current + 1);
  }

  const error = chat.messages.error ?? chat.create.error ?? chat.send.error ?? chat.undo.error;
  return (
    <div data-testid="vaic-miniapp-chat" style={{ display: "flex", flexDirection: "column", height: "100%", border: "1px solid var(--color-border)", borderRadius: "var(--radius-control)", background: "var(--color-surface)", overflow: "hidden" }}>
      <div style={{ padding: "var(--space-2) var(--space-3)", borderBottom: "1px solid var(--color-border)" }}>
        <ModelSelector
          providers={chat.models.data ?? []}
          providerId={chat.session?.provider_id ?? null}
          modelName={chat.session?.model_name ?? null}
          disabled={chat.pending}
          onChange={(providerId, modelName) => chat.changeModel.mutate({ providerId, modelName })}
        />
      </div>
      <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "var(--space-3)", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
        {messages.length === 0 && (
          <ChatBubble role="assistant" text="Mô tả thay đổi hoặc tải CSV/XLSX để sinh field/schema. Mọi thay đổi hợp lệ sẽ tự áp dụng và có thể Undo." />
        )}
        {messages.map((message) => (
          <ChatBubble
            key={message.id}
            role={message.role}
            text={message.status === "pending" ? "Đang tạo schema và kiểm tra…" : message.status === "failed" ? message.error?.message ?? "Không thể xử lý." : message.content}
            modelName={message.model_name}
            mutationId={typeof message.metadata.mutation_id === "string" ? message.metadata.mutation_id : undefined}
            onUndo={(id) => chat.undo.mutate(id)}
          />
        ))}
      </div>
      {error && <div role="alert" style={{ margin: "0 var(--space-3)", color: "var(--color-danger)", fontSize: 12 }}>{(error as Error).message}</div>}
      {isRebuilding && <div role="status" style={{ margin: "0 var(--space-3) var(--space-2)", fontSize: 12 }}>Đang rebuild preview…</div>}
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)", padding: "var(--space-3)", borderTop: "1px solid var(--color-border)" }}>
        <AttachmentPicker key={attachmentEpoch} disabled={chat.pending} onChange={onAttachmentsChange} />
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <input className="vaic-form-input vaic-focusable" style={{ flex: 1 }} placeholder="Mô tả thay đổi cho app…" value={input} onChange={(event) => setInput(event.target.value)} disabled={chat.pending} data-testid="vaic-miniapp-chat-input" />
          <Button variant="primary" type="submit" disabled={!input.trim() || chat.pending || !attachmentsReady || !chat.session}>Send</Button>
        </div>
      </form>
    </div>
  );
}

function ChatBubble({
  role,
  text,
  modelName,
  mutationId,
  onUndo,
}: {
  role: "user" | "assistant";
  text: string;
  modelName?: string | null;
  mutationId?: string;
  onUndo?: (id: string) => void;
}) {
  const isUser = role === "user";
  return (
    <div style={{ alignSelf: isUser ? "flex-end" : "flex-start", maxWidth: "85%", padding: "var(--space-2) var(--space-3)", borderRadius: "var(--radius-control)", background: isUser ? "var(--color-primary-soft)" : "var(--color-surface-muted)", color: "var(--color-text)", fontSize: "var(--text-body)", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
      {text}
      {modelName && <div style={{ marginTop: 4, fontSize: 10, opacity: 0.7 }}>{modelName}</div>}
      {mutationId && onUndo && <button type="button" onClick={() => onUndo(mutationId)} style={{ marginTop: 6 }}>Undo</button>}
    </div>
  );
}
