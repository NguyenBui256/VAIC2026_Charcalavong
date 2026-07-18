/* Chat tab (UI shell) — ChatGPT-style layout.
 * Left: conversation list. Right: message list + composer.
 * Mock replies, persisted to localStorage via useChat.
 */

import { useChat } from "../../lib/chatStore";
import ConversationList from "../../components/chat/conversation-list";
import MessageList from "../../components/chat/message-list";
import ChatComposer from "../../components/chat/chat-composer";

export default function ChatPage() {
  const {
    conversations,
    activeId,
    activeConversation,
    isTyping,
    selectConversation,
    newConversation,
    deleteConversation,
    sendMessage,
  } = useChat();

  return (
    <div style={{ display: "flex", height: "100%", minHeight: 0 }}>
      <ConversationList
        conversations={conversations}
        activeId={activeId}
        onSelect={selectConversation}
        onNew={newConversation}
        onDelete={deleteConversation}
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
        <MessageList
          messages={activeConversation?.messages ?? []}
          isTyping={isTyping}
        />
        <ChatComposer onSend={sendMessage} disabled={isTyping} />
      </div>
    </div>
  );
}
