/* Frontend-only left palette: drag Agents / a blank node onto the canvas,
 * toggle the edge view mode, and trigger vertical auto-layout. */

import { useAgents } from "../../../hooks/useAgents";
import { Button } from "../../ui";

export const NODE_DND_MIME = "application/x-vaic-node";

export type EdgeMode = "transition" | "rollback";

export interface PaletteSidebarProps {
  edgeMode: EdgeMode;
  onEdgeModeChange: (m: EdgeMode) => void;
  onAutoLayout: () => void;
}

function setDrag(e: React.DragEvent, payload: Record<string, unknown>) {
  e.dataTransfer.setData(NODE_DND_MIME, JSON.stringify(payload));
  e.dataTransfer.effectAllowed = "copy";
}

export default function PaletteSidebar({
  edgeMode,
  onEdgeModeChange,
  onAutoLayout,
}: PaletteSidebarProps) {
  const agents = useAgents({});
  return (
    <div
      style={{
        width: 220,
        flexShrink: 0,
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-3)",
        borderRight: "1px solid var(--color-border)",
        paddingRight: "var(--space-3)",
      }}
    >
      <div>
        <div className="vaic-form-label">Actions</div>
        <Button variant="secondary" onClick={onAutoLayout}>Sắp xếp dọc</Button>
      </div>

      <div>
        <div className="vaic-form-label">Chế độ edge</div>
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <Button
            variant={edgeMode === "transition" ? "primary" : "ghost"}
            onClick={() => onEdgeModeChange("transition")}
          >
            Transition
          </Button>
          <Button
            variant={edgeMode === "rollback" ? "primary" : "ghost"}
            onClick={() => onEdgeModeChange("rollback")}
          >
            Rollback
          </Button>
        </div>
      </div>

      <div>
        <div className="vaic-form-label">Kéo vào canvas</div>
        <div
          draggable
          onDragStart={(e) => setDrag(e, { kind: "blank" })}
          className="vaic-focusable"
          style={{
            padding: "6px 8px",
            border: "1px dashed var(--color-border)",
            borderRadius: 6,
            cursor: "grab",
            marginBottom: "var(--space-2)",
            fontSize: 13,
          }}
        >
          + Blank node
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 320, overflowY: "auto" }}>
          {(agents.data ?? []).map((a) => (
            <div
              key={a.id}
              draggable
              onDragStart={(e) => setDrag(e, { kind: "agent", agentId: a.id, name: a.name })}
              className="vaic-focusable"
              style={{
                padding: "6px 8px",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                cursor: "grab",
                fontSize: 13,
                background: "var(--color-surface, #fff)",
              }}
            >
              {a.name}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
