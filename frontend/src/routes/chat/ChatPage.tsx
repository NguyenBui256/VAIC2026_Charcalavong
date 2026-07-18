/* Chat tab (UI shell) — ChatGPT-style layout.
 * Flow: New chat → modal (pick Agent|Workflow + target) → conversation created
 * with the target locked. Header shows the locked target read-only (no switch).
 * Left: conversation list. Right (optional): progress/outputs side panel.
 * Mock replies, persisted to localStorage via useChat.
 */

import { useState } from "react";
import { PanelRight, Bot, Workflow as WorkflowIcon } from "lucide-react";
import { useChat } from "../../lib/chatStore";
import { useChatTargets } from "../../lib/chatTargets";
import ConversationList from "../../components/chat/conversation-list";
import MessageList from "../../components/chat/message-list";
import ChatComposer from "../../components/chat/chat-composer";
import ChatNewChatModal from "../../components/chat/chat-new-chat-modal";
import ChatSidePanel from "../../components/chat/chat-side-panel";

/** Read-only chip showing the conversation's locked target. */
function TargetChip({ type, name }: { type: "agent" | "workflow"; name: string }) {
  const Icon = type === "agent" ? Bot : WorkflowIcon;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "var(--space-2)",
        padding: "var(--space-1) var(--space-3)",
        borderRadius: "var(--radius-full, 9999px)",
        background: "var(--color-surface-muted)",
        color: "var(--color-text-secondary)",
        fontSize: "var(--text-caption)",
        fontWeight: 500,
      }}
    >
      <Icon size={14} strokeWidth={1.5} />
      <span style={{ color: "var(--color-text-tertiary)" }}>
        {type === "agent" ? "Agent" : "Workflow"}
      </span>
      <span style={{ fontWeight: 600, color: "var(--color-text-primary)" }}>{name}</span>
    </span>
  );
}

export default function ChatPage() {
  const {
    conversations,
    activeId,
    activeConversation,
    isTyping,
    selectConversation,
    createConversation,
    deleteConversation,
    renameConversation,
    sendMessage,
  } = useChat();
  const { agents, workflows, loading } = useChatTargets();
  const [showPanel, setShowPanel] = useState(false);
  const [showNewModal, setShowNewModal] = useState(false);

  const conv = activeConversation;
  const configured = Boolean(conv?.targetId && conv?.targetType);

  function handleStart(type: "agent" | "workflow", id: string, name: string) {
    createConversation(type, id, name);
    setShowNewModal(false);
  }

  return (
    <div style={{ display: "flex", height: "100%", minHeight: 0 }}>
      <ConversationList
        conversations={conversations}
        activeId={activeId}
        onSelect={selectConversation}
        onNew={() => setShowNewModal(true)}
        onDelete={deleteConversation}
        onRename={renameConversation}
      />

      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
          height: "100%",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "var(--space-3)",
            minHeight: "48px",
            padding: "var(--space-2) var(--space-4)",
            borderBottom: "1px solid var(--color-border)",
            background: "var(--color-surface)",
          }}
        >
          <div style={{ minWidth: 0 }}>
            {!conv ? (
              <span className="text-caption" style={{ color: "var(--color-text-tertiary)" }}>
                Click “New chat” to start
              </span>
            ) : configured && conv.targetType && conv.targetName ? (
              <TargetChip type={conv.targetType} name={conv.targetName} />
            ) : null}
          </div>

          <button
            type="button"
            onClick={() => setShowPanel((v) => !v)}
            aria-label="Toggle progress & outputs panel"
            title="Progress & Outputs"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: "32px",
              height: "32px",
              flexShrink: 0,
              borderRadius: "var(--radius-control, 6px)",
              border: "1px solid var(--color-border)",
              background: showPanel ? "var(--color-primary-soft)" : "var(--color-surface)",
              color: showPanel ? "var(--color-primary)" : "var(--color-text-secondary)",
              cursor: "pointer",
            }}
          >
            <PanelRight size={16} strokeWidth={1.5} />
          </button>
        </div>

        <MessageList messages={conv?.messages ?? []} isTyping={isTyping} />
        <ChatComposer onSend={sendMessage} disabled={isTyping || !conv} />
      </div>

      {showPanel && <ChatSidePanel targetType={conv?.targetType ?? null} />}

      <ChatNewChatModal
        open={showNewModal}
        agents={agents}
        workflows={workflows}
        loading={loading}
        onCancel={() => setShowNewModal(false)}
        onStart={handleStart}
      />
    </div>
  );
}
