/* Story 3.1 — Workflow detail shell (/workflows/:id): defaults to the
 * Definition tab (only tab in this story — Run history etc. arrive in
 * later stories). Header (name, Back), unsaved-changes guard (AC7).
 */

import { useNavigate } from "react-router-dom";
import { ErrorState, Skeleton, Button, ConfirmDialog } from "../ui";
import { semanticIcons, ICON_STROKE_WIDTH } from "../../lib/icons";
import { useWorkflow } from "../../hooks/useWorkflow";
import { useUnsavedChangesGuard } from "../agents/useUnsavedChangesGuard";
import DefinitionTab from "./DefinitionTab";
import RunsTab from "./RunsTab";
import GraphTab from "./graph/GraphTab";
import { useState } from "react";
import type { Workflow } from "../../lib/workflowsApi";

export interface WorkflowDetailShellProps {
  workflowId: string;
}

export default function WorkflowDetailShell({ workflowId }: WorkflowDetailShellProps) {
  const isNew = workflowId === "new";
  const navigate = useNavigate();
  const { query, data: workflow, isLoading, isError } = useWorkflow(
    isNew ? undefined : workflowId,
  );
  const [isDirty, setIsDirty] = useState(false);
  const [tab, setTab] = useState<"definition" | "graph" | "runs">("definition");

  const { guardedNavigate, confirmProps } = useUnsavedChangesGuard(isDirty);

  function handleBack() {
    guardedNavigate(() => navigate("/workflows"));
  }

  function handleSaved(saved: Workflow) {
    if (isNew) {
      navigate(`/workflows/${saved.id}`, { replace: true });
    }
  }

  const WorkflowIcon = semanticIcons.Orchestrator;

  return (
    <div data-testid="vaic-workflow-detail-shell" className="vaic-workflow-detail-shell">
      <header className="vaic-workflow-detail-header">
        <div className="vaic-workflow-detail-header-meta">
          <Button variant="ghost" onClick={handleBack}>
            Back to Workflows
          </Button>
          <h1
            className="text-h1"
            style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}
          >
            <WorkflowIcon size={20} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
            {isNew ? "New Workflow" : workflow?.name ?? "Workflow"}
          </h1>
        </div>
      </header>

      {isError && (
        <ErrorState
          message={query.error?.message ?? "Failed to load Workflow"}
          retry={
            <Button variant="secondary" onClick={() => query.refetch()}>
              Retry
            </Button>
          }
        />
      )}

      {!isError && !isNew && isLoading && (
        <div data-testid="vaic-workflow-detail-loading">
          <Skeleton lines={6} height="20px" />
        </div>
      )}

      {(isNew || (!isError && !isLoading)) && (
        <>
          <div
            role="tablist"
            style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}
          >
            <Button
              variant={tab === "definition" ? "primary" : "ghost"}
              onClick={() => setTab("definition")}
            >
              Definition
            </Button>
            <Button
              variant={tab === "graph" ? "primary" : "ghost"}
              disabled={isNew}
              onClick={() => guardedNavigate(() => { setIsDirty(false); setTab("graph"); })}
            >
              Graph
            </Button>
            <Button
              variant={tab === "runs" ? "primary" : "ghost"}
              disabled={isNew}
              onClick={() => guardedNavigate(() => { setIsDirty(false); setTab("runs"); })}
            >
              Runs
            </Button>
          </div>

          {tab === "definition" ? (
            <DefinitionTab
              workflowId={workflowId}
              isNew={isNew}
              workflow={workflow}
              onDirtyChange={setIsDirty}
              onSaved={handleSaved}
            />
          ) : tab === "graph" ? (
            <GraphTab workflowId={workflowId} />
          ) : (
            <RunsTab workflowId={workflowId} />
          )}
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
