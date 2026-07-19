/* Right column of the graph editor: a segmented Inspector|Chat toggle. */

import { useState } from "react";
import { Button } from "../../ui";
import NodeInspector, { type NodeInspectorProps } from "./NodeInspector";
import GraphChatPanel from "./GraphChatPanel";
import type { GraphChatMessage } from "../../../hooks/useGraphChat";
import type { ChatProvider, ChatSessionDto } from "../../../lib/chatApi";

interface Props {
  inspector: NodeInspectorProps;
  chat: {
    messages: GraphChatMessage[];
    onSend: (text: string, attachmentIds?: string[]) => void;
    pending: boolean;
    providers: ChatProvider[];
    session: ChatSessionDto | null;
    onModelChange: (providerId: string, modelName: string) => void;
    onUndo: (mutationId: string) => void;
    error?: string;
  };
}

export default function GraphRightPanel({ inspector, chat }: Props) {
  const [view, setView] = useState<"inspector" | "chat">("inspector");
  return (
    <div style={{ width: 320, flexShrink: 0, display: "flex", flexDirection: "column", minHeight: 0, borderLeft: "1px solid var(--color-border)", paddingLeft: "var(--space-3)" }}>
      <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
        <Button variant={view === "inspector" ? "primary" : "ghost"} onClick={() => setView("inspector")}>
          Inspector
        </Button>
        <Button variant={view === "chat" ? "primary" : "ghost"} onClick={() => setView("chat")}>
          Chat
        </Button>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflowY: view === "inspector" ? "auto" : "hidden" }}>
        {view === "inspector" ? <NodeInspector {...inspector} /> : <GraphChatPanel {...chat} />}
      </div>
    </div>
  );
}
