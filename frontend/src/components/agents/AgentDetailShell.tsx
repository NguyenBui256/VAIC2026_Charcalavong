/* Story 2.2 — Agent detail shell: 6-tab nav (AC #5, #6, #10, #11). */

import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button, Skeleton, ErrorState, ConfirmDialog } from "../ui";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../lib/icons";
import { useAgent } from "../../hooks/useAgent";
import { useUnsavedChangesGuard } from "./useUnsavedChangesGuard";
import IdentityTab from "./IdentityTab";
import KnowledgeBaseTab from "./tabs/KnowledgeBaseTab";
import ToolsTab from "./tabs/ToolsTab";
import ApiIntegrationsTab from "./tabs/ApiIntegrationsTab";
import PromptTab from "./tabs/PromptTab";
import ModelTab from "./tabs/ModelTab";

const TABS = [
  { key: "identity", label: "Identity" },
  { key: "knowledge-base", label: "Knowledge Base" },
  { key: "tools", label: "Tools" },
  { key: "api-integrations", label: "API Integrations" },
  { key: "prompt", label: "Prompt" },
  { key: "model", label: "Model" },
] as const;

type TabKey = (typeof TABS)[number]["key"];
const DEFAULT_TAB: TabKey = "identity";

export interface AgentDetailShellProps {
  agentId: string;
}

export default function AgentDetailShell({ agentId }: AgentDetailShellProps) {
  const isNew = agentId === "new";
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedTab = searchParams.get("tab");
  const activeTab: TabKey = TABS.some((t) => t.key === requestedTab)
    ? (requestedTab as TabKey)
    : DEFAULT_TAB;

  const [isIdentityDirty, setIsIdentityDirty] = useState(false);
  const [isModelDirty, setIsModelDirty] = useState(false);
  const [isPromptDirty, setIsPromptDirty] = useState(false);
  const isAnyTabDirty = isIdentityDirty || isModelDirty || isPromptDirty;
  const { guardedNavigate, confirmProps } = useUnsavedChangesGuard(isAnyTabDirty);

  const { query, data: agent, isLoading, isError } = useAgent(isNew ? undefined : agentId);

  const AgentIcon = semanticIcons.Agent;

  function handleTabChange(tab: TabKey) {
    guardedNavigate(() => setSearchParams({ tab }));
  }

  function handleBack() {
    guardedNavigate(() => navigate("/agents"));
  }

  function handleSaved(saved: { id: string }) {
    if (isNew) {
      navigate(`/agents/${saved.id}`, { replace: true });
    }
  }

  const showTabs = isNew || (!isError && !isLoading);

  return (
    <div data-testid="vaic-agent-detail-shell">
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "var(--space-3)",
          marginBottom: "var(--space-4)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
          <Button variant="ghost" onClick={handleBack}>
            Back to Agents
          </Button>
        </div>
        <h1
          className="text-h1"
          style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}
        >
          <AgentIcon size={20} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
          {isNew ? "New Agent" : agent?.name ?? "Agent"}
        </h1>
      </header>

      {isError && (
        <ErrorState
          message={query.error?.message ?? "Failed to load Agent"}
          retry={
            <Button variant="secondary" onClick={() => query.refetch()}>
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
          <nav
            className="vaic-tabs"
            role="tablist"
            aria-label="Agent configuration"
          >
            {TABS.map((tab) => (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.key}
                className={`vaic-tab vaic-focusable ${activeTab === tab.key ? "vaic-tab-active" : ""}`}
                onClick={() => handleTabChange(tab.key)}
                data-testid={`vaic-tab-${tab.key}`}
              >
                {tab.label}
                {((tab.key === "identity" && isIdentityDirty) ||
                  (tab.key === "model" && isModelDirty) ||
                  (tab.key === "prompt" && isPromptDirty)) && (
                  <span
                    className="vaic-dirty-dot"
                    aria-label="Unsaved changes"
                    data-testid="vaic-dirty-dot"
                  />
                )}
              </button>
            ))}
          </nav>

          <div className="vaic-tab-panel" role="tabpanel">
            {activeTab === "identity" && (
              <IdentityTab
                agentId={agentId}
                isNew={isNew}
                agent={agent}
                onDirtyChange={setIsIdentityDirty}
                onSaved={handleSaved}
              />
            )}
            {activeTab === "knowledge-base" && <KnowledgeBaseTab agentId={agentId} isNew={isNew} />}
            {activeTab === "tools" && <ToolsTab agentId={agentId} isNew={isNew} />}
            {activeTab === "api-integrations" && (
              <ApiIntegrationsTab agentId={agentId} isNew={isNew} />
            )}
            {activeTab === "prompt" && (
              <PromptTab
                agentId={agentId}
                isNew={isNew}
                agent={agent}
                onDirtyChange={setIsPromptDirty}
              />
            )}
            {activeTab === "model" && (
              <ModelTab
                agentId={agentId}
                isNew={isNew}
                agent={agent}
                onDirtyChange={setIsModelDirty}
              />
            )}
          </div>
        </>
      )}

      <ConfirmDialog
        {...confirmProps}
        title="Discard unsaved changes?"
        body="You have unsaved changes. Leaving now will discard them."
        confirmLabel="Discard"
        cancelLabel="Keep editing"
      />
    </div>
  );
}
