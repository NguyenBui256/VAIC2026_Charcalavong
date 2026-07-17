/* Story 2.8 T2.3 — detail-view header: name, Department badge, status pill,
 * global "Save All" (AC #8). Single Primary CTA per UX-DR3 — Save All is the
 * shell's Primary; the per-tab Save buttons remain Secondary-weight in
 * their own view (only one is mounted at a time alongside this header).
 */

import { Button, useToast } from "../ui";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../lib/icons";
import AgentStatusPill from "./AgentStatusPill";
import DepartmentBadge from "./DepartmentBadge";
import { useAgentBuilder } from "./AgentBuilderContext";
import type { Agent } from "../../lib/agentsApi";

export interface AgentDetailHeaderProps {
  isNew: boolean;
  agent: Agent | undefined;
  departmentName: string | undefined;
  onBack: () => void;
  /** Suppress the Save All button (UX-DR3 — a modal with its own Primary,
   * e.g. the tab-switch guard, is currently open). */
  suppressSaveAll?: boolean;
}

export default function AgentDetailHeader({
  isNew,
  agent,
  departmentName,
  onBack,
  suppressSaveAll = false,
}: AgentDetailHeaderProps) {
  const AgentIcon = semanticIcons.Agent;
  const { anyDirty, saveAll } = useAgentBuilder();
  const { show } = useToast();

  async function handleSaveAll() {
    try {
      await saveAll();
      show("All changes saved");
    } catch (err) {
      show(err instanceof Error ? err.message : "Failed to save changes", "error");
    }
  }

  return (
    <header className="vaic-agent-detail-header">
      <div className="vaic-agent-detail-header-meta">
        <Button variant="ghost" onClick={onBack}>
          Back to Agents
        </Button>
        <h1
          className="text-h1"
          style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}
        >
          <AgentIcon size={20} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
          {isNew ? "New Agent" : agent?.name ?? "Agent"}
        </h1>
        {!isNew && departmentName && <DepartmentBadge name={departmentName} />}
        {!isNew && agent && <AgentStatusPill status={agent.status} />}
      </div>

      {!isNew && anyDirty && !suppressSaveAll && (
        <Button variant="primary" onClick={handleSaveAll} data-testid="vaic-save-all">
          Save All
        </Button>
      )}
    </header>
  );
}
