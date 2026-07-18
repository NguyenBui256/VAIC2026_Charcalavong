/* Story 2.8 T1.1 — the ordered six-tab registry (UX-DR16).
 *
 * Single source of truth for the Agent Builder surface: drives the tab-nav
 * render order/labels/icons AND the count-badge lookup (`countKey`). The
 * registry never imports a tab component directly (that would create an
 * import cycle with AgentDetailShell) — components are wired in
 * AgentDetailShell's own switch, keyed by `TabKey`.
 */

import { semanticIcons, type SemanticConcept } from "../../lib/icons";
import type { TabCounts, TabKey } from "./agentBuilderTypes";

export interface TabRegistryEntry {
  key: TabKey;
  label: string;
  icon: SemanticConcept;
  /** Key into `TabCounts` this tab's badge reads, or undefined if uncountable. */
  countKey?: keyof TabCounts;
}

export const tabRegistry: TabRegistryEntry[] = [
  { key: "identity", label: "Identity", icon: "Agent" },
  { key: "knowledge-base", label: "Knowledge Base", icon: "KnowledgeBase", countKey: "documents" },
  { key: "tools", label: "Tools", icon: "Tool", countKey: "tools" },
  { key: "prompt", label: "Prompt", icon: "Prompt" },
  { key: "model", label: "Model", icon: "Model" },
];

/** Look up a registry entry's icon component. */
export function tabIcon(entry: TabRegistryEntry) {
  return semanticIcons[entry.icon];
}
