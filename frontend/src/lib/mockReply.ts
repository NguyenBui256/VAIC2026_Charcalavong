/* Mock reply generator for the Chat UI shell (no backend).
 * Echoes user text + a fixed markdown/code demo so the UI can show off
 * markdown rendering, code blocks, lists, etc.
 */

export interface ChatTarget {
  type: "agent" | "workflow";
  name: string;
}

/** Build the full markdown reply text for a given user message. */
export function generateMockReply(
  userText: string,
  target?: ChatTarget | null,
): string {
  const trimmed = userText.trim();
  const targetLine = target
    ? [`> Chatting with **${target.type === "agent" ? "agent" : "workflow"}** \`${target.name}\``, ""]
    : [];
  return [
    ...targetLine,
    `You said: **${trimmed || "(empty)"}**`,
    "",
    "This is a *demo* reply (no backend yet). It supports:",
    "",
    "- **Bold**, *italic*, `inline code` formatting",
    "- Lists and headings",
    "- Code blocks with syntax highlighting:",
    "",
    "```ts",
    "function greet(name: string) {",
    "  return `Hello, ${name}!`;",
    "}",
    "```",
    "",
    "> Agent/backend integration is coming later.",
  ].join("\n");
}

/**
 * Stream `full` text chunk-by-chunk to simulate typing.
 * Calls onChunk with the accumulated string; onDone when finished.
 * Returns a cancel function to stop early (call on unmount / new send).
 */
export function streamText(
  full: string,
  onChunk: (partial: string) => void,
  onDone: () => void,
): () => void {
  const STEP = 3; // characters per tick
  const INTERVAL_MS = 16;
  let i = 0;
  const timer = setInterval(() => {
    i = Math.min(full.length, i + STEP);
    onChunk(full.slice(0, i));
    if (i >= full.length) {
      clearInterval(timer);
      onDone();
    }
  }, INTERVAL_MS);
  return () => clearInterval(timer);
}
