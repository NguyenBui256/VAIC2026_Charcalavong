/* Deterministic parser for the graph-editing chat panel. No AI: maps a small
 * set of EN + VN command phrases to structured GraphCommand objects. The
 * caller (GraphTab) resolves node/agent references and performs the mutation. */

export type GraphCommand =
  | { kind: "add_node"; label: string }
  | { kind: "assign_agent"; nodeRef: string; agentName: string }
  | { kind: "connect"; from: string; to: string }
  | { kind: "delete_node"; nodeRef: string }
  | { kind: "list" }
  | { kind: "help" }
  | { kind: "unknown" };

/** Normalize separators used in "connect A -> B": ->, →, or the word "to". */
function splitConnect(rest: string): [string, string] | null {
  const m = rest.match(/^(.+?)\s*(?:->|→|\bto\b)\s*(.+)$/i);
  if (!m) return null;
  const from = m[1].trim();
  const to = m[2].trim();
  if (!from || !to) return null;
  return [from, to];
}

export function parseGraphCommand(text: string): GraphCommand {
  const t = text.trim();
  const lower = t.toLowerCase();

  if (lower === "help" || lower === "?" || lower === "trợ giúp") {
    return { kind: "help" };
  }
  if (lower === "list" || lower === "danh sách" || lower === "liệt kê") {
    return { kind: "list" };
  }

  // add node <label> | thêm node <label>
  let m = t.match(/^(?:add node|thêm node)\s+(.+)$/i);
  if (m) return { kind: "add_node", label: m[1].trim() };

  // set agent <agentName> on <node> | gán agent <agentName> cho <node>
  m = t.match(/^(?:set agent|gán agent)\s+(.+?)\s+(?:on|cho)\s+(.+)$/i);
  if (m) return { kind: "assign_agent", agentName: m[1].trim(), nodeRef: m[2].trim() };

  // connect <A> -> <B> | nối <A> -> <B>
  m = t.match(/^(?:connect|nối|noi)\s+(.+)$/i);
  if (m) {
    const pair = splitConnect(m[1]);
    if (pair) return { kind: "connect", from: pair[0], to: pair[1] };
  }

  // delete node <node> | xoá node <node> | xóa node <node>
  m = t.match(/^(?:delete node|xoá node|xóa node|remove node)\s+(.+)$/i);
  if (m) return { kind: "delete_node", nodeRef: m[1].trim() };

  return { kind: "unknown" };
}
