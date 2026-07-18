/* Mock reply generator for the Chat UI shell (no backend).
 * Echoes user text + a fixed markdown/code demo so the UI can show off
 * markdown rendering, code blocks, lists, etc.
 */

/** Build the full markdown reply text for a given user message. */
export function generateMockReply(userText: string): string {
  const trimmed = userText.trim();
  return [
    `Bạn vừa nói: **${trimmed || "(trống)"}**`,
    "",
    "Đây là phản hồi *demo* (chưa nối backend). Mình hỗ trợ:",
    "",
    "- Định dạng **đậm**, *nghiêng*, `inline code`",
    "- Danh sách và tiêu đề",
    "- Khối code có syntax highlight:",
    "",
    "```ts",
    "function greet(name: string) {",
    "  return `Xin chào, ${name}!`;",
    "}",
    "```",
    "",
    "> Kết nối agent/backend sẽ được thêm sau.",
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
  const STEP = 3; // ký tự mỗi tick
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
