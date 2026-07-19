/* Fake-stream a string chunk-by-chunk to simulate typing in the chat.
 * Calls onChunk with the accumulated text; onDone at the end. Returns a
 * cancel fn (call on unmount / before a new stream). */
export function streamText(
  full: string,
  onChunk: (partial: string) => void,
  onDone: () => void,
): () => void {
  const STEP = 3;
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
