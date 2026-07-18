/* Local (non-persisted) chat state for the graph-editing side panel. Each
 * send() parses the text, runs the command via the injected resolver, and
 * records the user message + the resolver's reply. No backend, no streaming. */

import { useCallback, useState } from "react";
import { parseGraphCommand } from "../lib/graphChatCommands";

export interface GraphChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

let seq = 0;
function nextId(): string {
  seq += 1;
  return `gcm-${seq}`;
}

const WELCOME =
  'Type a command to edit the flow. Try "help". Examples: "add node Review", ' +
  '"gán agent Reviewer cho Review", "connect Step 1 -> Step 2", "delete node Review".';

export function useGraphChat(opts: { run: (cmd: ReturnType<typeof parseGraphCommand>) => string }) {
  const { run } = opts;
  const [messages, setMessages] = useState<GraphChatMessage[]>([
    { id: nextId(), role: "assistant", content: WELCOME },
  ]);

  const send = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      const cmd = parseGraphCommand(trimmed);
      const reply = run(cmd);
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "user", content: trimmed },
        { id: nextId(), role: "assistant", content: reply },
      ]);
    },
    [run],
  );

  return { messages, send };
}
