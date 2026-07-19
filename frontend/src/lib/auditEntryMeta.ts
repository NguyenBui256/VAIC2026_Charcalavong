/* Epic 6 (FR-22) — audit entry type → icon + label + accent, for the Trace
 * timeline. Uses the locked semantic icons (lib/icons.tsx). Unknown types fall
 * back to the generic Trace icon so a new backend entry type still renders.
 */

import type { LucideIcon } from "lucide-react";
import { semanticIcons } from "./icons";

export interface AuditEntryMeta {
  icon: LucideIcon;
  /** Human label for the entry type. */
  label: string;
  /** CSS custom property driving the timeline dot / accent color. */
  colorVar: string;
}

const META_BY_TYPE: Record<string, AuditEntryMeta> = {
  decomposition: { icon: semanticIcons.Orchestrator, label: "Decomposition", colorVar: "var(--color-accent)" },
  task_dispatch: { icon: semanticIcons.Action, label: "Task dispatch", colorVar: "var(--color-accent)" },
  tool_call: { icon: semanticIcons.Tool, label: "Tool call", colorVar: "var(--color-running)" },
  model_invocation: { icon: semanticIcons.Model, label: "Model invocation", colorVar: "var(--color-running)" },
  aggregation: { icon: semanticIcons.Orchestrator, label: "Aggregation", colorVar: "var(--color-accent)" },
  escalation: { icon: semanticIcons.Escalation, label: "Escalation", colorVar: "var(--color-escalated)" },
  mini_app_emission: { icon: semanticIcons.MiniApp, label: "Mini-App emission", colorVar: "var(--color-success)" },
  retrieval: { icon: semanticIcons.KnowledgeBase, label: "KB retrieval", colorVar: "var(--color-running)" },
};

/** Prefix mappings for dotted/namespaced types (e.g. "workflow.created"). */
const META_BY_PREFIX: [string, AuditEntryMeta][] = [
  ["workflow_run.", { icon: semanticIcons.Orchestrator, label: "Run transition", colorVar: "var(--color-accent)" }],
  ["workflow.", { icon: semanticIcons.Orchestrator, label: "Workflow CRUD", colorVar: "var(--color-text-tertiary)" }],
  ["agent.", { icon: semanticIcons.Agent, label: "Agent CRUD", colorVar: "var(--color-text-tertiary)" }],
  ["tool.", { icon: semanticIcons.Tool, label: "Tool CRUD", colorVar: "var(--color-text-tertiary)" }],
  ["integration.", { icon: semanticIcons.ApiIntegration, label: "Integration", colorVar: "var(--color-text-tertiary)" }],
];

const FALLBACK: AuditEntryMeta = {
  icon: semanticIcons.Trace,
  label: "Event",
  colorVar: "var(--color-text-tertiary)",
};

export function auditEntryMeta(type: string): AuditEntryMeta {
  const exact = META_BY_TYPE[type];
  if (exact) return exact;
  for (const [prefix, meta] of META_BY_PREFIX) {
    if (type.startsWith(prefix)) return meta;
  }
  return { ...FALLBACK, label: prettifyType(type) };
}

/** "task_dispatch" / "workflow.created" → "Task dispatch" / "Workflow created". */
function prettifyType(type: string): string {
  const words = type.replace(/[._]/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
