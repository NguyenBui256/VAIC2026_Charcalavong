/* Chat tab (UI shell) — ChatGPT-style layout.
 * Left: conversation list. Middle: header (target selector + panel toggle)
 * + message list + composer. Right (optional): progress/outputs side panel.
 * Mock replies, persisted to localStorage via useChat.
 */

import { useState } from "react";
import { PanelRight } from "lucide-react";
import { useChat } from "../../lib/chatStore";
import { useChatTargets } from "../../lib/chatTargets";
import ConversationList from "../../components/chat/conversation-list";
import MessageList from "../../components/chat/message-list";
import ChatComposer from "../../components/chat/chat-composer";
import ChatTargetSelector from "../../components/chat/chat-target-selector";
import ChatSidePanel from "../../components/chat/chat-side-panel";

export default function ChatPage() {
  const {
    conversations,
    activeId,
    activeConversation,
    isTyping,
    selectConversation,
    newConversation,
    deleteConversation,
    renameConversation,
    setTarget,
    sendMessage,
  } = useChat();
  const { agents, workflows, loading } = useChatTargets();
  const [showPanel, setShowPanel] = useState(false);

  return (
    <div style={{ display: "flex", height: "100%", minHeight: 0 }}>
      <ConversationList
        conversations={conversations}
        activeId={activeId}
        onSelect={selectConversation}
        onNew={newConversation}
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
            padding: "var(--space-2) var(--space-4)",
            borderBottom: "1px solid var(--color-border)",
            background: "var(--color-surface)",
          }}
        >
          {activeId ? (
            <ChatTargetSelector
              targetType={activeConversation?.targetType ?? null}
              targetId={activeConversation?.targetId ?? null}
              agents={agents}
              workflows={workflows}
              loading={loading}
              onChange={(type, id, name) => setTarget(activeId, type, id || null, name || null)}
            />
          ) : (
            <span
              className="text-caption"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              Tạo/chọn hội thoại trước
            </span>
          )}

          <button
            type="button"
            onClick={() => setShowPanel((v) => !v)}
            aria-label="Bật/tắt panel tiến độ & kết quả"
            title="Tiến độ & Kết quả"
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: "32px",
              height: "32px",
              borderRadius: "var(--radius-control, 6px)",
              border: "1px solid var(--color-border)",
              background: showPanel ? "var(--color-primary-soft)" : "var(--color-surface)",
              color: showPanel ? "var(--color-primary)" : "var(--color-text-secondary)",
              cursor: "pointer",
              flexShrink: 0,
            }}
          >
            <PanelRight size={16} strokeWidth={1.5} />
          </button>
        </div>

        <MessageList
          messages={activeConversation?.messages ?? []}
          isTyping={isTyping}
        />
        <ChatComposer onSend={sendMessage} disabled={isTyping} />
      </div>

      {showPanel && (
        <ChatSidePanel targetType={activeConversation?.targetType ?? null} />
      )}
    </div>
  );
}
