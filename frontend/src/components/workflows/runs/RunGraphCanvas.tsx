/* 3C — hand-rolled SVG DAG canvas. Edges drawn as paths (parent bottom-center
 * → child top-center) on an SVG layer; nodes are absolutely-positioned boxes
 * on top. No graph library; positions come from layout.ts.
 */
import RunNode from "./RunNode";
import { NODE_H, NODE_W, layoutPositions } from "./layout";
import type { MergedNode } from "./mergeNodes";
import type { GraphEdge } from "../../../lib/runsApi";

export interface RunGraphCanvasProps {
  nodes: MergedNode[];
  edges: GraphEdge[];
  selectedKey: string | null;
  onSelect: (nodeKey: string) => void;
  pendingRollbackKeys: Set<string>;
}

export default function RunGraphCanvas({
  nodes,
  edges,
  selectedKey,
  onSelect,
  pendingRollbackKeys,
}: RunGraphCanvasProps) {
  const pos = layoutPositions(nodes, edges);
  let maxX = 0;
  let maxY = 0;
  pos.forEach((p) => {
    maxX = Math.max(maxX, p.x + NODE_W);
    maxY = Math.max(maxY, p.y + NODE_H);
  });
  const width = maxX + 40;
  const height = maxY + 40;

  return (
    <div
      data-testid="vaic-run-graph-canvas"
      style={{
        position: "relative",
        width,
        height,
        minWidth: "100%",
        overflow: "auto",
      }}
    >
      <svg
        width={width}
        height={height}
        style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
      >
        <defs>
          <marker
            id="vaic-arrow"
            markerWidth="8"
            markerHeight="8"
            refX="6"
            refY="3"
            orient="auto"
          >
            <path d="M0,0 L6,3 L0,6 Z" fill="var(--color-border-strong, #888)" />
          </marker>
        </defs>
        {edges.map((e) => {
          const a = pos.get(e.from);
          const b = pos.get(e.to);
          if (!a || !b) return null;
          const x1 = a.x + NODE_W / 2;
          const y1 = a.y + NODE_H;
          const x2 = b.x + NODE_W / 2;
          const y2 = b.y;
          const midY = (y1 + y2) / 2;
          return (
            <path
              key={`${e.from}->${e.to}`}
              d={`M${x1},${y1} C${x1},${midY} ${x2},${midY} ${x2},${y2}`}
              fill="none"
              stroke="var(--color-border-strong, #888)"
              strokeWidth={1.5}
              markerEnd="url(#vaic-arrow)"
            />
          );
        })}
      </svg>
      {nodes.map((n) => {
        const p = pos.get(n.node_key) ?? { x: 0, y: 0 };
        return (
          <RunNode
            key={n.node_key}
            node={n}
            x={p.x}
            y={p.y}
            selected={selectedKey === n.node_key}
            hasPendingRollback={pendingRollbackKeys.has(n.node_key)}
            onSelect={onSelect}
          />
        );
      })}
    </div>
  );
}
