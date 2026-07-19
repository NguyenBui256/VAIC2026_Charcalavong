/* Epic 6 (FR-23) — collaboration graph view of the Audit Trail.
 *
 * Orchestrator node at the top, Specialist Agent nodes below, edges labelled
 * with each agent's step count (types in the node's tooltip). Pure inline SVG
 * — no external graph lib (CSP-safe). Reads the same audit entries as the
 * timeline; scope it to one Run (via the /audit run_id filter) for a clean
 * single-workflow collaboration picture.
 */

import type { CollaborationGraph as Graph } from "../../lib/collaborationGraph";

export interface CollaborationGraphProps {
  graph: Graph;
}

const NODE_W = 176;
const NODE_H = 56;
const ORCH_Y = 28;
const AGENT_Y = 228;
const HEIGHT = 312;
const MIN_WIDTH = 640;
const COL_W = 208;

function truncate(text: string, max = 20): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export default function CollaborationGraph({ graph }: CollaborationGraphProps) {
  const { orchestratorSteps, agents } = graph;
  const width = Math.max(MIN_WIDTH, agents.length * COL_W);
  const orchX = width / 2;
  const orchTopX = orchX - NODE_W / 2;
  const edgeStartY = ORCH_Y + NODE_H;

  const agentCenters = agents.map(
    (_, i) => ((i + 0.5) * width) / Math.max(agents.length, 1),
  );

  return (
    <div style={{ overflowX: "auto" }} data-testid="vaic-collab-graph">
      <svg
        viewBox={`0 0 ${width} ${HEIGHT}`}
        width={width}
        height={HEIGHT}
        role="img"
        aria-label={`Collaboration graph: Orchestrator and ${agents.length} agent(s)`}
        style={{ maxWidth: "100%", height: "auto" }}
      >
        {/* Edges Orchestrator → each Agent. */}
        {agents.map((agent, i) => {
          const ax = agentCenters[i];
          const midY = (edgeStartY + AGENT_Y) / 2;
          const path = `M ${orchX} ${edgeStartY} C ${orchX} ${edgeStartY + 60}, ${ax} ${AGENT_Y - 60}, ${ax} ${AGENT_Y}`;
          return (
            <g key={`edge-${agent.agentId}`}>
              <path
                d={path}
                fill="none"
                style={{ stroke: "var(--color-border)" }}
                strokeWidth={1.5}
              />
              <g transform={`translate(${(orchX + ax) / 2}, ${midY})`}>
                <rect
                  x={-34}
                  y={-11}
                  width={68}
                  height={22}
                  rx={11}
                  style={{ fill: "var(--color-surface)", stroke: "var(--color-border)" }}
                  strokeWidth={1}
                />
                <text
                  x={0}
                  y={4}
                  textAnchor="middle"
                  style={{ fill: "var(--color-text-secondary)", fontSize: 11 }}
                >
                  {agent.steps} step{agent.steps === 1 ? "" : "s"}
                </text>
              </g>
            </g>
          );
        })}

        {/* Orchestrator node. */}
        <GraphNode
          x={orchTopX}
          y={ORCH_Y}
          title="Orchestrator"
          subtitle={`${orchestratorSteps} step${orchestratorSteps === 1 ? "" : "s"}`}
          accentVar="var(--color-accent)"
        />

        {/* Agent nodes. */}
        {agents.map((agent, i) => (
          <GraphNode
            key={agent.agentId}
            x={agentCenters[i] - NODE_W / 2}
            y={AGENT_Y}
            title={truncate(agent.label)}
            subtitle={`${agent.steps} step${agent.steps === 1 ? "" : "s"}`}
            accentVar="var(--color-running)"
            tooltip={`${agent.label}\nTypes: ${agent.types.join(", ") || "—"}`}
          />
        ))}
      </svg>
    </div>
  );
}

interface GraphNodeProps {
  x: number;
  y: number;
  title: string;
  subtitle: string;
  accentVar: string;
  tooltip?: string;
}

function GraphNode({ x, y, title, subtitle, accentVar, tooltip }: GraphNodeProps) {
  return (
    <g>
      {tooltip && <title>{tooltip}</title>}
      <rect
        x={x}
        y={y}
        width={NODE_W}
        height={NODE_H}
        rx={10}
        style={{ fill: "var(--color-surface)", stroke: accentVar }}
        strokeWidth={2}
      />
      <circle cx={x + 18} cy={y + NODE_H / 2} r={5} style={{ fill: accentVar }} />
      <text
        x={x + 34}
        y={y + 24}
        style={{ fill: "var(--color-text-primary)", fontSize: 14, fontWeight: 600 }}
      >
        {title}
      </text>
      <text
        x={x + 34}
        y={y + 42}
        style={{ fill: "var(--color-text-tertiary)", fontSize: 12 }}
      >
        {subtitle}
      </text>
    </g>
  );
}
