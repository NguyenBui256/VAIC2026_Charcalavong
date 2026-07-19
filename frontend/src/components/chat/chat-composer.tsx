/* Message composer: auto-growing textarea. Enter sends, Shift+Enter newline.
 * Disabled while the bot is "typing".
 */

import { useCallback, useRef, useState, type KeyboardEvent } from "react";
import { SendHorizontal } from "lucide-react";
import AttachmentPicker from "./attachment-picker";

interface Props {
  onSend: (text: string, attachmentIds?: string[]) => void;
  disabled: boolean;
}

export default function ChatComposer({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");
  const [attachmentIds, setAttachmentIds] = useState<string[]>([]);
  const [attachmentsReady, setAttachmentsReady] = useState(true);
  const [attachmentEpoch, setAttachmentEpoch] = useState(0);
  const ref = useRef<HTMLTextAreaElement | null>(null);

  function autoGrow() {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  function submit() {
    const text = value.trim();
    if (!text || disabled || !attachmentsReady) return;
    onSend(text, attachmentIds);
    setValue("");
    setAttachmentIds([]);
    setAttachmentsReady(true);
    setAttachmentEpoch((current) => current + 1);
    if (ref.current) ref.current.style.height = "auto";
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
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-end",
        gap: "var(--space-2)",
        padding: "var(--space-3) var(--space-6)",
        borderTop: "1px solid var(--color-border)",
        background: "var(--color-surface)",
      }}
    >
      <AttachmentPicker
        key={attachmentEpoch}
        disabled={disabled}
        onChange={onAttachmentsChange}
      />
      <div style={{ display: "flex", alignItems: "flex-end", gap: "var(--space-2)", width: "100%" }}>
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          autoGrow();
        }}
        onKeyDown={onKeyDown}
        rows={1}
        placeholder="Type a message… (Enter to send, Shift+Enter for a new line)"
        style={{
          flex: 1,
          resize: "none",
          maxHeight: "160px",
          padding: "var(--space-2) var(--space-3)",
          borderRadius: "var(--radius-control, 8px)",
          border: "1px solid var(--color-border)",
          background: "var(--color-surface)",
          color: "var(--color-text-primary)",
          fontSize: "var(--text-body)",
          fontFamily: "inherit",
          lineHeight: 1.5,
          outline: "none",
        }}
      />
      <button
        type="button"
        onClick={submit}
        disabled={disabled || !value.trim() || !attachmentsReady}
        aria-label="Send"
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: "40px",
          height: "40px",
          flexShrink: 0,
          borderRadius: "var(--radius-control, 8px)",
          border: "none",
          background: "var(--color-primary)",
          color: "var(--color-primary-contrast, #fff)",
          cursor: disabled || !value.trim() || !attachmentsReady ? "not-allowed" : "pointer",
          opacity: disabled || !value.trim() || !attachmentsReady ? 0.5 : 1,
        }}
      >
        <SendHorizontal size={18} strokeWidth={1.5} />
      </button>
      </div>
    </div>
  );
}
