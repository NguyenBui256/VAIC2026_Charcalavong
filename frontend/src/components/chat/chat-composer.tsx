/* Message composer: auto-growing textarea. Enter sends, Shift+Enter newline.
 * Disabled while the bot is "typing".
 */

import { useRef, useState, type KeyboardEvent } from "react";
import { SendHorizontal } from "lucide-react";

interface Props {
  onSend: (text: string) => void;
  disabled: boolean;
}

export default function ChatComposer({ onSend, disabled }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement | null>(null);

  function autoGrow() {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  function submit() {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
    if (ref.current) ref.current.style.height = "auto";
  }

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
        alignItems: "flex-end",
        gap: "var(--space-2)",
        padding: "var(--space-3) var(--space-6)",
        borderTop: "1px solid var(--color-border)",
        background: "var(--color-surface)",
      }}
    >
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
        disabled={disabled || !value.trim()}
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
          cursor: disabled || !value.trim() ? "not-allowed" : "pointer",
          opacity: disabled || !value.trim() ? 0.5 : 1,
        }}
      >
        <SendHorizontal size={18} strokeWidth={1.5} />
      </button>
    </div>
  );
}
