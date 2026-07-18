/* Right column of the chat page — fixed width, shows Progress + Outputs
 * sections for the active conversation's target. Toggled from ChatPage.
 */

import ProgressPanel from "./progress-panel";
import OutputsPanel from "./outputs-panel";

interface Props {
  targetType: "agent" | "workflow" | null;
}

const SECTION_HEADER_STYLE = {
  fontSize: "var(--text-caption)",
  fontWeight: 600,
  color: "var(--color-text-tertiary)",
  textTransform: "uppercase" as const,
  letterSpacing: "0.02em",
  marginBottom: "var(--space-2)",
};

export default function ChatSidePanel({ targetType }: Props) {
  return (
    <div
      style={{
        width: "300px",
        flexShrink: 0,
        borderLeft: "1px solid var(--color-border)",
        background: "var(--color-surface)",
        height: "100%",
        overflowY: "auto",
        padding: "var(--space-4)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-5)",
      }}
    >
      <section>
        <div style={SECTION_HEADER_STYLE}>Tiến độ (Progress)</div>
        <ProgressPanel targetType={targetType} />
      </section>

      <section>
        <div style={SECTION_HEADER_STYLE}>Kết quả (Outputs)</div>
        <OutputsPanel />
      </section>
    </div>
  );
}
