/* Story 2.8 — Agent Builder surface: upgrades the Story 2.2 6-tab scaffold
 * into one cohesive shell driven by `tabRegistry` (AC #1), with count
 * badges (AC #2), per-tab dirty dots (AC #3), switch-with-unsaved
 * confirmation (AC #4), new-Agent tab gating (AC #7), a header with
 * Department badge/status pill/Save All (AC #8), and roving-tabindex
 * keyboard nav (AC #9). See Dev Notes "Scope Boundaries" — this file
 * ORCHESTRATES the six tabs; it does not re-implement their feature logic.
 */

import { useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Info } from "lucide-react";
import { ErrorState, Skeleton, Button, ConfirmDialog } from "../ui";
import { ICON_STROKE_WIDTH } from "../../lib/icons";
import { useAgent } from "../../hooks/useAgent";
import { useDepartments } from "../../hooks/useDepartments";
import { useUnsavedChangesGuard } from "./useUnsavedChangesGuard";
import { AgentBuilderProvider, useAgentBuilder } from "./AgentBuilderContext";
import { useTabSwitchGuard } from "./TabSwitchGuard";
import { useTabCounts } from "./useTabCounts";
import { tabRegistry } from "./tabRegistry";
import AgentTabNav from "./AgentTabNav";
import AgentDetailHeader from "./AgentDetailHeader";
import IdentityTab from "./IdentityTab";
import KnowledgeBaseTab from "./tabs/KnowledgeBaseTab";
import ToolsTab from "./tabs/ToolsTab";
import ApiIntegrationsTab from "./tabs/ApiIntegrationsTab";
import PromptTab from "./tabs/PromptTab";
import ModelTab from "./tabs/ModelTab";
import type { TabKey } from "./agentBuilderTypes";
import type { Agent } from "../../lib/agentsApi";

const DEFAULT_TAB: TabKey = "identity";
const ALL_TAB_KEYS = tabRegistry.map((t) => t.key);

export interface AgentDetailShellProps {
  agentId: string;
}

export default function AgentDetailShell({ agentId }: AgentDetailShellProps) {
  const isNew = agentId === "new";
  const navigate = useNavigate();
  const { query, data: agent, isLoading, isError } = useAgent(isNew ? undefined : agentId);

  function handleSaved(saved: { id: string }) {
    if (isNew) {
      navigate(`/agents/${saved.id}?tab=identity`, { replace: true });
    }
  }

  return (
    <div data-testid="vaic-agent-detail-shell" className="vaic-agent-detail-shell">
      <div className="vaic-agent-detail-main">
        <AgentBuilderProvider>
          <AgentDetailShellBody
            agentId={agentId}
            isNew={isNew}
            agent={agent}
            isLoading={isLoading}
            isError={isError}
            errorMessage={query.error?.message}
            onRetry={() => query.refetch()}
            onSaved={handleSaved}
            navigate={navigate}
          />
        </AgentBuilderProvider>
      </div>
    </div>
  );
}

interface AgentDetailShellBodyProps {
  agentId: string;
  isNew: boolean;
  agent: Agent | undefined;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string | undefined;
  onRetry: () => void;
  onSaved: (saved: { id: string }) => void;
  navigate: ReturnType<typeof useNavigate>;
}

function AgentDetailShellBody({
  agentId,
  isNew,
  agent,
  isLoading,
  isError,
  errorMessage,
  onRetry,
  onSaved,
  navigate,
}: AgentDetailShellBodyProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const activeTab: TabKey = ALL_TAB_KEYS.includes(requestedTab as TabKey)
    ? (requestedTab as TabKey)
    : DEFAULT_TAB;

  const { dirtyTabs, anyDirty } = useAgentBuilder();
  const { data: departments } = useDepartments();
  const counts = useTabCounts(isNew ? undefined : agentId);

  const { guardedNavigate, confirmProps } = useUnsavedChangesGuard(anyDirty);
  const { guardedTabChange, dialog: switchDialog } = useTabSwitchGuard((tab) =>
    setSearchParams({ tab }),
  );

  // AC #7 — new-Agent gating: only Identity is enabled until the record exists.
  const disabledTabs = useMemo(
    () => new Set<TabKey>(isNew ? ALL_TAB_KEYS.filter((k) => k !== "identity") : []),
    [isNew],
  );

  const departmentName = agent
    ? departments?.find((d) => d.id === agent.department_id)?.name
    : undefined;

  function handleTabChange(tab: TabKey) {
    guardedTabChange(activeTab, tab);
  }

  function handleBack() {
    guardedNavigate(() => navigate("/agents"));
  }

  const showTabs = isNew || (!isError && !isLoading);

  return (
    <>
      <AgentDetailHeader
        isNew={isNew}
        agent={agent}
        departmentName={departmentName}
        onBack={handleBack}
      />

      {isError && (
        <ErrorState
          message={errorMessage ?? "Failed to load Agent"}
          retry={
            <Button variant="secondary" onClick={onRetry}>
              Retry
            </Button>
          }
        />
      )}

      {!isError && !isNew && isLoading && (
        <div data-testid="vaic-agent-detail-loading">
          <Skeleton lines={6} height="20px" />
        </div>
      )}

      {showTabs && (
        <>
          {isNew && (
            <div className="vaic-agent-gating-note" role="note">
              <Info
                size={16}
                strokeWidth={ICON_STROKE_WIDTH}
                className="vaic-agent-gating-note-icon"
                aria-hidden="true"
              />
              <span>
                Start with the <strong>Identity</strong> basics. Once you create the Agent,
                Knowledge Base, Tools, API Integrations, Prompt and Model unlock.
              </span>
            </div>
          )}

          <div className="vaic-agent-builder-layout">
            <aside className="vaic-agent-builder-nav">
              <AgentTabNav
                activeTab={activeTab}
                onTabChange={handleTabChange}
                disabledTabs={disabledTabs}
                dirtyTabs={dirtyTabs}
                counts={counts}
              />
            </aside>

            <div className="vaic-agent-builder-content">
              <div
                className="vaic-tab-panel"
                role="tabpanel"
                aria-labelledby={`vaic-tab-${activeTab}`}
              >
                {activeTab === "identity" && (
                  <IdentityTab
                    agentId={agentId}
                    isNew={isNew}
                    agent={agent}
                    onDirtyChange={() => {}}
                    onSaved={onSaved}
                    onCancelNew={handleBack}
                  />
                )}
                {activeTab === "knowledge-base" && (
                  <KnowledgeBaseTab agentId={agentId} isNew={isNew} />
                )}
                {activeTab === "tools" && <ToolsTab agentId={agentId} isNew={isNew} />}
                {activeTab === "api-integrations" && (
                  <ApiIntegrationsTab agentId={agentId} isNew={isNew} />
                )}
                {activeTab === "prompt" && (
                  <PromptTab agentId={agentId} isNew={isNew} agent={agent} onDirtyChange={() => {}} />
                )}
                {activeTab === "model" && (
                  <ModelTab agentId={agentId} isNew={isNew} agent={agent} onDirtyChange={() => {}} />
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {switchDialog}

      {/* Full-page nav (Back to Agents / browser back) uses the simpler
          two-button Discard/Keep-editing dialog — the three-button
          Save/Discard/Cancel variant is reserved for in-surface tab
          switches (AC #4), which have a specific tab to save/discard. */}
      <ConfirmDialog
        {...confirmProps}
        title="Discard unsaved changes?"
        body="You have unsaved changes. Leaving now will discard them."
        confirmLabel="Discard"
        cancelLabel="Keep editing"
      />
    </>
  );
}
