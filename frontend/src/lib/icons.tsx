/* Story 1.9 — Locked semantic icon assignments (UX-DR10, UX-DR11).
 *
 * `lucide-react` is the only icon library used in VAIC.
 * Stroke width is 1.5px globally per the design system.
 *
 * This file is the SINGLE SOURCE OF TRUTH for:
 *  1. Concept → icon mapping (UX-DR10 semantic assignments).
 *  2. Run/Task state → {icon, color token, label} mapping (UX-DR11).
 *
 * Components MUST import from here rather than reaching into lucide-react
 * directly for semantic concepts. This keeps icon+color mapping consistent
 * across every surface (StatusPill, Dashboard, Run View, Audit, etc.).
 *
 * No emojis are used as structural icons (UX-DR10).
 */

import {
  Activity,
  AlertTriangle,
  Bot,
  BookOpen,
  Building2,
  Check,
  Clock,
  Cpu,
  LayoutGrid,
  Landmark,
  Loader,
  Pencil,
  Play,
  Plug,
  Radio,
  Webhook,
  Wrench,
  Workflow,
  Zap,
  FileSearch,
  Library,
  AppWindow,
  type LucideIcon,
} from "lucide-react";

/* ──────────────────────────────────────────────────────────────────────────
 * UX-DR10 — Semantic concept → icon assignments (LOCKED).
 * Do NOT reassign. Adding new concepts is fine; reassigning existing ones
 * breaks visual consistency across the product.
 * ──────────────────────────────────────────────────────────────────────── */

export const semanticIcons = {
  /** Specialist Agent. */
  Agent: Bot,
  /** Workflow Orchestrator. */
  Orchestrator: Workflow,
  /** Mini-App (catalog / grid). */
  MiniApp: LayoutGrid,
  /** Mini-App alternative (single window). */
  MiniAppAlt: AppWindow,
  /** Trace / Audit timeline. */
  Trace: Activity,
  /** Audit / file search. */
  AuditSearch: FileSearch,
  /** Action / Trigger. */
  Action: Zap,
  /** Knowledge Base (open book). */
  KnowledgeBase: BookOpen,
  /** Knowledge Base alternative (library shelf). */
  KnowledgeBaseAlt: Library,
  /** Tool (callable by agent). */
  Tool: Wrench,
  /** API Integration (plug). */
  ApiIntegration: Plug,
  /** API Integration alternative (webhook). */
  Webhook: Webhook,
  /** LLM Model. */
  Model: Cpu,
  /** Department (org unit). */
  Department: Building2,
  /** Tenant (bank). */
  Tenant: Landmark,
  /** Run (execute workflow). */
  Run: Play,
  /** Escalation (human review needed). */
  Escalation: AlertTriangle,
  /** Live stream / in-flight. */
  Live: Radio,
} as const;

export type SemanticConcept = keyof typeof semanticIcons;

/* ──────────────────────────────────────────────────────────────────────────
 * UX-DR11 — Run / Task state mapping (LOCKED).
 *
 * The same icon + color token + label MUST be used everywhere a state appears:
 * StatusPill, Dashboard KPI, Run View step, Audit trail row, toast, etc.
 * ──────────────────────────────────────────────────────────────────────── */

export type RunState =
  | "pending"
  | "running"
  | "success"
  | "error"
  | "escalated"
  | "draft";

export interface StateMapping {
  /** Lucide icon component. */
  icon: LucideIcon;
  /** CSS custom property for the icon/text color, e.g. `var(--color-pending)`. */
  colorVar: string;
  /** CSS custom property for the soft background tint, e.g. `var(--color-pending-soft)`. */
  softVar: string;
  /** Human-readable label shown next to the icon. */
  label: string;
  /** When true, the icon spins (only the `running` state). */
  spin: boolean;
}

export const stateMapping: Record<RunState, StateMapping> = {
  pending: {
    icon: Clock,
    colorVar: "var(--color-pending)",
    softVar: "var(--color-pending-soft)",
    label: "Pending",
    spin: false,
  },
  running: {
    icon: Loader,
    colorVar: "var(--color-running)",
    softVar: "var(--color-running-soft)",
    label: "Running",
    spin: true,
  },
  success: {
    icon: Check,
    colorVar: "var(--color-success)",
    softVar: "var(--color-success-soft)",
    label: "Success",
    spin: false,
  },
  error: {
    icon: AlertTriangle,
    colorVar: "var(--color-error)",
    softVar: "var(--color-error-soft)",
    label: "Error",
    spin: false,
  },
  escalated: {
    icon: AlertTriangle,
    colorVar: "var(--color-escalated)",
    softVar: "var(--color-escalated-soft)",
    label: "Escalated",
    spin: false,
  },
  draft: {
    icon: Pencil,
    colorVar: "var(--slate-400)",
    softVar: "var(--color-surface-muted)",
    label: "Draft",
    spin: false,
  },
};

/** Ordered list of all RunStates — useful for tests and iteration. */
export const allRunStates: RunState[] = [
  "pending",
  "running",
  "success",
  "error",
  "escalated",
  "draft",
];

/** Default lucide stroke width enforced globally (UX-DR10). */
export const ICON_STROKE_WIDTH = 1.5;
