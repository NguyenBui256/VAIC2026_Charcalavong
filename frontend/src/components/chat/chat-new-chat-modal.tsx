/* New-chat modal: pick mode (Agent|Workflow) + a specific target, then start.
 * The conversation is created only on confirm; the target is locked for its
 * lifetime. Reuses the overlay/dialog pattern + motion from ConfirmDialog.
 */

import { useEffect, useRef, useState } from "react";
import { durations, easings } from "../../lib/motion";
import { Button } from "../ui";
import type { ChatTargetOption } from "../../lib/chatTargets";
import ChatTargetSelector from "./chat-target-selector";

type TargetType = "agent" | "workflow";

interface Props {
  open: boolean;
  agents: ChatTargetOption[];
  workflows: ChatTargetOption[];
  loading: boolean;
  onCancel: () => void;
  onStart: (type: TargetType, id: string, name: string) => void;
}

export default function ChatNewChatModal({
  open,
  agents,
  workflows,
  loading,
  onCancel,
  onStart,
}: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [type, setType] = useState<TargetType>("agent");
  const [id, setId] = useState("");
  const [name, setName] = useState("");

  // Reset the draft each time the modal opens; Esc closes; focus the dialog.
  useEffect(() => {
    if (!open) return;
    setType("agent");
    setId("");
    setName("");
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    const t = window.setTimeout(() => dialogRef.current?.focus(), 0);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.clearTimeout(t);
    };
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      role="presentation"
      className="vaic-confirm-overlay"
      style={{
        animationDuration: `${durations.modal}ms`,
        animationTimingFunction: easings.modal,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="vaic-new-chat-title"
        tabIndex={-1}
        className="vaic-confirm-dialog"
        style={{
          animationDuration: `${durations.modal}ms`,
          animationTimingFunction: easings.modal,
        }}
      >
        <h3 id="vaic-new-chat-title" className="text-h3">
          New conversation
        </h3>
        <p className="text-body" style={{ color: "var(--color-text-tertiary)", textWrap: "pretty" }}>
          Choose a mode and target. This stays fixed for the whole
          conversation.
        </p>

        <div style={{ margin: "var(--space-3) 0" }}>
          <ChatTargetSelector
            targetType={type}
            targetId={id || null}
            agents={agents}
            workflows={workflows}
            loading={loading}
            onChange={(t, i, n) => {
              setType(t);
              setId(i);
              setName(n);
            }}
          />
        </div>

        <div className="vaic-confirm-actions">
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="primary" disabled={!id} onClick={() => id && onStart(type, id, name)}>
            Start chat
          </Button>
        </div>
      </div>
    </div>
  );
}
