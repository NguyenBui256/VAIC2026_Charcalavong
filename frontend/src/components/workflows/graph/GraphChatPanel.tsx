/* Chat panel for the graph editor's right column. Renders the message log and
 * a composer; delegates command execution to the injected `send`. */

import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { SendHorizontal } from "lucide-react";
import type { GraphChatMessage } from "../../../hooks/useGraphChat";
import AttachmentPicker from "../../chat/attachment-picker";

interface Props {
  messages: GraphChatMessage[];
  onSend: (text: string, attachmentIds?: string[]) => void;
  pending: boolean;
  onUndo: (mutationId: string) => void;
  error?: string;
}

export default function GraphChatPanel({ messages, onSend, pending, onUndo, error }: Props) {
  const [value, setValue] = useState("");
  const [attachmentIds, setAttachmentIds] = useState<string[]>([]);
  const [attachmentsReady, setAttachmentsReady] = useState(true);
  const [attachmentEpoch, setAttachmentEpoch] = useState(0);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  function submit() {
    const text = value.trim();
    if (!text || pending || !attachmentsReady) return;
    onSend(text, attachmentIds);
    setValue("");
    setAttachmentIds([]);
    setAttachmentsReady(true);
    setAttachmentEpoch((current) => current + 1);
  }

  const onAttachmentsChange = useCallback((ids: string[], ready: boolean) => {
    setAttachmentIds(ids);
    setAttachmentsReady(ready);
  }, []);

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "var(--space-2)", paddingBottom: "var(--space-2)" }}>
        {messages.map((m) => (
          <div
            key={m.id}
            style={{
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "90%",
              padding: "6px 10px",
              borderRadius: 8,
              fontSize: 13,
              whiteSpace: "pre-wrap",
              background: m.role === "user" ? "var(--color-primary)" : "var(--color-surface-muted, #f1f1f1)",
              color: m.role === "user" ? "var(--color-primary-contrast, #fff)" : "var(--color-text-primary)",
              border: m.role === "user" ? "none" : "1px solid var(--color-border)",
            }}
          >
            {m.status === "pending" ? "Đang phân tích và kiểm tra graph…" : m.status === "failed" ? m.error?.message ?? "Không thể xử lý." : m.content}
            {typeof m.metadata.mutation_id === "string" && (
              <button type="button" onClick={() => onUndo(m.metadata.mutation_id as string)} style={{ display: "block", marginTop: 6 }}>Undo</button>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      {error && <div role="alert" style={{ color: "var(--color-danger)", fontSize: 12 }}>{error}</div>}
      <AttachmentPicker key={attachmentEpoch} disabled={pending} onChange={onAttachmentsChange} />
      <div style={{ display: "flex", alignItems: "flex-end", gap: "var(--space-2)", paddingTop: "var(--space-2)", borderTop: "1px solid var(--color-border)" }}>
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          placeholder="Mô tả quy trình hoặc đính kèm DOCX/PDF đặc tả…"
          disabled={pending}
          style={{
            flex: 1,
            resize: "none",
            padding: "var(--space-2)",
            borderRadius: 8,
            border: "1px solid var(--color-border)",
            background: "var(--color-surface)",
            color: "var(--color-text-primary)",
            fontSize: 13,
            fontFamily: "inherit",
            outline: "none",
          }}
        />
        <button
          type="button"
          onClick={submit}
          disabled={!value.trim() || pending || !attachmentsReady}
          aria-label="Send"
          style={{
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            width: 36, height: 36, flexShrink: 0, borderRadius: 8, border: "none",
            background: "var(--color-primary)", color: "var(--color-primary-contrast, #fff)",
            cursor: value.trim() ? "pointer" : "not-allowed", opacity: value.trim() ? 1 : 0.5,
          }}
        >
          <SendHorizontal size={16} strokeWidth={1.5} />
        </button>
      </div>
    </div>
  );
}
