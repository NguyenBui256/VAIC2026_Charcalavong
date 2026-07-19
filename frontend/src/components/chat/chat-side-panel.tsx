import type { ChatMessage } from "../../lib/chatStore";
import RunTrackingView from "../workflows/runs/RunTrackingView";

export default function ChatSidePanel({
  targetType,
  runId,
  messages,
}: {
  targetType: "agent" | "workflow" | null;
  runId?: string;
  messages: ChatMessage[];
}) {
  const last = [...messages].reverse().find((message) => message.role === "assistant");
  return (
    <aside style={{ width: 360, flexShrink: 0, borderLeft: "1px solid var(--color-border)", background: "var(--color-surface)", height: "100%", overflowY: "auto", padding: "var(--space-4)" }}>
      {targetType === "workflow" ? (
        runId ? <RunTrackingView runId={runId} /> : <p className="text-caption">Run sẽ xuất hiện sau khi gửi tin nhắn.</p>
      ) : (
        <>
          <h3 className="text-caption">Kết quả & nguồn</h3>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
            {last ? JSON.stringify(last.metadata ?? {}, null, 2) : "Chưa có kết quả."}
          </pre>
        </>
      )}
    </aside>
  );
}
