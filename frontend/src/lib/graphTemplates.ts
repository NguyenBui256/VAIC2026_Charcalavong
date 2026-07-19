/* Frontend-defined starter graphs for new workflows. Each build() returns a
 * GraphDefinition whose nodes have an EMPTY agent_id — the user fills agents
 * in the graph editor after creation. Positions are hand-laid top->bottom so
 * no layout pass is needed at seed time. */

import type {
  GraphDefinition,
  GraphDefinitionNode,
} from "./workflowGraphApi";

/** How a new workflow's graph should be seeded (chosen in NewWorkflowModal). */
export type CreateSeed =
  | { kind: "blank" }
  | { kind: "template"; templateId: string; defaultName: string }
  | { kind: "duplicate"; sourceId: string; def: GraphDefinition; defaultName: string };

export interface GraphTemplate {
  id: string;
  name: string;
  description: string;
  build(): GraphDefinition;
}

const ROW = 160;
const COL = 240;

/** Blank node with the given key/label at (x,y). agent_id intentionally "". */
function node(key: string, label: string, x: number, y: number): GraphDefinitionNode {
  return {
    node_key: key,
    label,
    agent_id: "",
    config: {},
    position: { x, y },
    approver_user_ids: [],
  };
}

export const GRAPH_TEMPLATES: GraphTemplate[] = [
  {
    id: "linear",
    name: "Linear pipeline",
    description: "Three steps in sequence: A → B → C.",
    build: () => ({
      nodes: [
        node("n1", "Step 1", 0, 0),
        node("n2", "Step 2", 0, ROW),
        node("n3", "Step 3", 0, ROW * 2),
      ],
      edges: [
        { from: "n1", to: "n2" },
        { from: "n2", to: "n3" },
      ],
    }),
  },
  {
    id: "approval",
    name: "Approval chain",
    description: "Task → Review → Approve.",
    build: () => ({
      nodes: [
        node("n1", "Task", 0, 0),
        node("n2", "Review", 0, ROW),
        node("n3", "Approve", 0, ROW * 2),
      ],
      edges: [
        { from: "n1", to: "n2" },
        { from: "n2", to: "n3" },
      ],
    }),
  },
  {
    id: "fanout",
    name: "Fan-out / Fan-in",
    description: "One source fans out to two branches, then joins.",
    build: () => ({
      nodes: [
        node("n1", "Source", 0, 0),
        node("n2", "Branch 1", -COL / 2, ROW),
        node("n3", "Branch 2", COL / 2, ROW),
        node("n4", "Join", 0, ROW * 2),
      ],
      edges: [
        { from: "n1", to: "n2" },
        { from: "n1", to: "n3" },
        { from: "n2", to: "n4" },
        { from: "n3", to: "n4" },
      ],
    }),
  },
];

export function getTemplate(id: string): GraphTemplate | undefined {
  return GRAPH_TEMPLATES.find((t) => t.id === id);
}
