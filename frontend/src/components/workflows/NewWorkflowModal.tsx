/* "Start from" modal for creating a workflow: Blank, a Template, or Duplicate
 * an existing workflow. On confirm it resolves a CreateSeed (fetching the
 * source graph for Duplicate) and hands it back to the caller. */

import { useEffect, useRef, useState } from "react";
import { durations, easings } from "../../lib/motion";
import { Button } from "../ui";
import { useWorkflows } from "../../hooks/useWorkflows";
import { getWorkflowGraph } from "../../lib/workflowGraphApi";
import { GRAPH_TEMPLATES, type CreateSeed } from "../../lib/graphTemplates";

type Mode = "blank" | "template" | "duplicate";

interface Props {
  open: boolean;
  onCancel: () => void;
  onConfirm: (seed: CreateSeed) => void;
}

export default function NewWorkflowModal({ open, onCancel, onConfirm }: Props) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<Mode>("blank");
  const [templateId, setTemplateId] = useState(GRAPH_TEMPLATES[0]?.id ?? "");
  const [sourceId, setSourceId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: workflows } = useWorkflows({});

  useEffect(() => {
    if (!open) return;
    setMode("blank");
    setTemplateId(GRAPH_TEMPLATES[0]?.id ?? "");
    setSourceId("");
    setBusy(false);
    setError(null);
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    const t = window.setTimeout(() => dialogRef.current?.focus(), 0);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.clearTimeout(t);
    };
  }, [open, onCancel]);

  if (!open) return null;

  async function confirm() {
    setError(null);
    if (mode === "blank") {
      onConfirm({ kind: "blank" });
      return;
    }
    if (mode === "template") {
      const t = GRAPH_TEMPLATES.find((x) => x.id === templateId);
      if (!t) {
        setError("Pick a template.");
        return;
      }
      onConfirm({ kind: "template", templateId: t.id, defaultName: t.name });
      return;
    }
    // duplicate
    const src = (workflows ?? []).find((w) => w.id === sourceId);
    if (!src) {
      setError("Pick a workflow to duplicate.");
      return;
    }
    try {
      setBusy(true);
      const def = await getWorkflowGraph(src.id);
      onConfirm({
        kind: "duplicate",
        sourceId: src.id,
        def,
        defaultName: `${src.name} (copy)`,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load source graph");
    } finally {
      setBusy(false);
    }
  }

  const modeButton = (m: Mode, label: string) => (
    <Button variant={mode === m ? "primary" : "ghost"} onClick={() => setMode(m)}>
      {label}
    </Button>
  );

  return (
    <div
      role="presentation"
      className="vaic-confirm-overlay"
      style={{ animationDuration: `${durations.modal}ms`, animationTimingFunction: easings.modal }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="vaic-new-wf-title"
        tabIndex={-1}
        className="vaic-confirm-dialog"
        style={{ animationDuration: `${durations.modal}ms`, animationTimingFunction: easings.modal }}
      >
        <h3 id="vaic-new-wf-title" className="text-h3">Start a new workflow</h3>
        <p className="text-body" style={{ color: "var(--color-text-tertiary)", textWrap: "pretty" }}>
          Start from scratch, a template, or by duplicating an existing workflow.
        </p>

        <div style={{ display: "flex", gap: "var(--space-2)", margin: "var(--space-3) 0" }}>
          {modeButton("blank", "Blank")}
          {modeButton("template", "Template")}
          {modeButton("duplicate", "Duplicate")}
        </div>

        {mode === "template" && (
          <div className="vaic-form-field">
            <label className="vaic-form-label">Template</label>
            <select
              className="vaic-form-input vaic-focusable"
              value={templateId}
              onChange={(e) => setTemplateId(e.target.value)}
            >
              {GRAPH_TEMPLATES.map((t) => (
                <option key={t.id} value={t.id}>{t.name} — {t.description}</option>
              ))}
            </select>
          </div>
        )}

        {mode === "duplicate" && (
          <div className="vaic-form-field">
            <label className="vaic-form-label">Duplicate from</label>
            <select
              className="vaic-form-input vaic-focusable"
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
            >
              <option value="">— choose workflow —</option>
              {(workflows ?? []).map((w) => (
                <option key={w.id} value={w.id}>{w.name}</option>
              ))}
            </select>
          </div>
        )}

        {error && (
          <div className="vaic-inline-alert" role="alert" style={{ marginTop: "var(--space-2)" }}>
            {error}
          </div>
        )}

        <div className="vaic-confirm-actions">
          <Button variant="secondary" onClick={onCancel}>Cancel</Button>
          <Button variant="primary" disabled={busy} onClick={confirm}>
            {busy ? "Loading…" : "Continue"}
          </Button>
        </div>
      </div>
    </div>
  );
}
