/* Story 2.8 T2.3 — detail-view header: breadcrumb back link, title with icon,
 * Department badge + status pill. Saving is per-tab (view → Edit → Save/Cancel),
 * so the header is purely orientation/identity — no global save control.
 */

import { ChevronLeft } from "lucide-react";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../lib/icons";
import AgentStatusPill from "./AgentStatusPill";
import DepartmentBadge from "./DepartmentBadge";
import type { Agent } from "../../lib/agentsApi";

export interface AgentDetailHeaderProps {
  isNew: boolean;
  agent: Agent | undefined;
  departmentName: string | undefined;
  onBack: () => void;
}

export default function AgentDetailHeader({
  isNew,
  agent,
  departmentName,
  onBack,
}: AgentDetailHeaderProps) {
  const AgentIcon = semanticIcons.Agent;

  return (
    <header className="vaic-agent-detail-header">
      <button type="button" className="vaic-agent-detail-breadcrumb vaic-focusable" onClick={onBack}>
        <ChevronLeft size={14} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
        Agents
      </button>

      <div className="vaic-agent-detail-title">
        <AgentIcon size={22} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
        <h1 className="text-h1">{isNew ? "New Agent" : agent?.name ?? "Agent"}</h1>
      </div>

      {!isNew && (departmentName || agent) && (
        <div className="vaic-agent-detail-header-meta">
          {departmentName && <DepartmentBadge name={departmentName} />}
          {agent && <AgentStatusPill status={agent.status} />}
        </div>
      )}
    </header>
  );
}
