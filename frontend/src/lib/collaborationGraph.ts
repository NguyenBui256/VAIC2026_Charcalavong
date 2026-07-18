/* Epic 6 (FR-23) — build a collaboration graph from Audit Trail entries.
 *
 * Pure, testable transform: entries → { orchestrator, agents[] }. The
 * Orchestrator aggregates entries with no agent_id (decomposition, dispatch,
 * aggregation — logged agent_id=NULL). Each distinct agent_id becomes a
 * Specialist Agent node. Edges (Orchestrator→Agent) carry the agent's step
 * count + the distinct entry types it produced (PRD FR-23).
 */

import type { AuditEntry } from "./auditApi";

export interface GraphAgentNode {
  agentId: string;
  /** Display label — agent name if resolvable, else short id. */
  label: string;
  /** Number of audit steps this agent produced. */
  steps: number;
  /** Distinct entry types, in first-seen order (edge/label detail). */
  types: string[];
}

export interface CollaborationGraph {
  orchestratorSteps: number;
  agents: GraphAgentNode[];
  totalSteps: number;
}

/**
 * @param entries   audit rows (already filtered/scoped by the caller)
 * @param nameById  optional agent_id → name map for nicer labels
 */
export function buildCollaborationGraph(
  entries: AuditEntry[],
  nameById?: Map<string, string>,
): CollaborationGraph {
  let orchestratorSteps = 0;
  // Preserve first-seen order of agents for stable, meaningful layout.
  const order: string[] = [];
  const byAgent = new Map<string, { steps: number; types: string[] }>();

  for (const entry of entries) {
    if (!entry.agent_id) {
      orchestratorSteps += 1;
      continue;
    }
    let node = byAgent.get(entry.agent_id);
    if (!node) {
      node = { steps: 0, types: [] };
      byAgent.set(entry.agent_id, node);
      order.push(entry.agent_id);
    }
    node.steps += 1;
    if (entry.type && !node.types.includes(entry.type)) {
      node.types.push(entry.type);
    }
  }

  const agents: GraphAgentNode[] = order.map((agentId) => {
    const node = byAgent.get(agentId)!;
    return {
      agentId,
      label: nameById?.get(agentId) ?? `${agentId.slice(0, 8)}…`,
      steps: node.steps,
      types: node.types,
    };
  });

  const agentSteps = agents.reduce((sum, a) => sum + a.steps, 0);
  return {
    orchestratorSteps,
    agents,
    totalSteps: orchestratorSteps + agentSteps,
  };
}
